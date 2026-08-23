import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:linkchat_mobile/models/file_transfer.dart';
import 'package:linkchat_mobile/models/peer.dart';
import 'package:linkchat_mobile/network/connection_manager.dart';
import 'package:linkchat_mobile/network/discovery_service.dart';
import 'package:linkchat_mobile/network/protocol.dart';
import 'package:linkchat_mobile/services/file_transfer_service.dart';
import 'package:linkchat_mobile/services/identity_service.dart';

/// End-to-end tests of the actual protocol over real sockets on this
/// machine -- as close to a two-phone field test as a single host can get
/// without hardware. No mocks: real RawDatagramSocket/ServerSocket/Socket,
/// real X25519 handshake, real ChaCha20-Poly1305 encryption, real chunked
/// file I/O.
///
/// Note on discovery: two RawDatagramSockets bound to the *same* UDP port
/// in the same process don't reliably fan out broadcast datagrams to both
/// on Windows (SO_REUSEADDR here behaves as "last bind wins", unlike
/// Linux's SO_REUSEPORT) -- that's a same-host testing artifact, not a
/// real-deployment bug: on two actual phones each has its own independent
/// network stack, so there's no port to share. The discovery test below
/// instead proves the beacon wire format itself (a plain unicast UDP
/// datagram parsed by the real [DiscoveryService] listener); the
/// chat/file test bypasses discovery and drives [ConnectionManager]
/// directly with [Peer]s built from each side's real bound port.
void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  // file_transfer_service.dart calls path_provider's
  // getApplicationDocumentsDirectory(), which needs a real platform to
  // answer that MethodChannel call. Point it at a real temp directory
  // instead of mocking the transfer logic itself.
  late Directory fakeDocsDir;
  setUpAll(() {
    fakeDocsDir = Directory.systemTemp.createTempSync('linkchat_docs_');
    TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger
        .setMockMethodCallHandler(
      const MethodChannel('plugins.flutter.io/path_provider'),
      (call) async =>
          call.method == 'getApplicationDocumentsDirectory' ? fakeDocsDir.path : null,
    );
  });
  tearDownAll(() => fakeDocsDir.deleteSync(recursive: true));

  test('DiscoveryService parses a real incoming beacon datagram', () async {
    final identityB = IdentityService.fixed('peer-b', 'Bob');
    final discoveryB =
        DiscoveryService(identity: identityB, tcpPortProvider: () => 9999);
    await discoveryB.start();
    addTearDown(discoveryB.dispose);

    final sender = await RawDatagramSocket.bind(InternetAddress.anyIPv4, 0);
    addTearDown(sender.close);

    final beacon = utf8.encode(jsonEncode(
        {'t': 'hello', 'id': 'peer-a', 'name': 'Alice', 'tcp': 12345}));
    sender.send(beacon, InternetAddress.loopbackIPv4, DiscoveryService.discoveryPort);

    final peerA = await discoveryB.peers
        .expand((list) => list)
        .firstWhere((p) => p.id == 'peer-a')
        .timeout(const Duration(seconds: 20));

    expect(peerA.name, 'Alice');
    expect(peerA.tcpPort, 12345);
  });

  test('two peers exchange an encrypted chat message and a file over real TCP',
      () async {
    final identityA = IdentityService.fixed('peer-a', 'Alice');
    final identityB = IdentityService.fixed('peer-b', 'Bob');

    final connectionsA = ConnectionManager(identity: identityA);
    final connectionsB = ConnectionManager(identity: identityB);
    await connectionsA.start();
    await connectionsB.start();

    final ftA = FileTransferService(connections: connectionsA);
    final ftB = FileTransferService(connections: connectionsB);

    Directory? tmpDir;
    addTearDown(() async {
      ftA.dispose();
      ftB.dispose();
      connectionsA.dispose();
      connectionsB.dispose();
      if (tmpDir != null) {
        await tmpDir.delete(recursive: true);
      }
    });

    // Peers as each side would learn them from discovery -- built directly
    // here since same-host UDP broadcast fan-out is unreliable (see file
    // header), but every byte from this point on goes over a real socket.
    final peerB = Peer(
      id: 'peer-b',
      name: 'Bob',
      address: InternetAddress.loopbackIPv4,
      tcpPort: connectionsB.tcpPort,
      lastSeen: DateTime.now(),
    );
    final peerA = Peer(
      id: 'peer-a',
      name: 'Alice',
      address: InternetAddress.loopbackIPv4,
      tcpPort: connectionsA.tcpPort,
      lastSeen: DateTime.now(),
    );
    expect(peerB.tcpPort, greaterThan(0));
    expect(peerA.tcpPort, greaterThan(0));

    // --- Real TCP connect + X25519 handshake + encrypted chat frame ---
    final chatReceived = Completer<Map<String, dynamic>>();
    connectionsB.inboundFrames.listen((inbound) {
      final (peerId, frame) = inbound;
      if (frame.type == InnerType.chat &&
          peerId == 'peer-a' &&
          !chatReceived.isCompleted) {
        chatReceived.complete(
            jsonDecode(utf8.decode(frame.payload)) as Map<String, dynamic>);
      }
    });

    final delivered = await connectionsA.send(
      peerB,
      InnerType.chat,
      utf8.encode(jsonEncode(
          {'id': 'm1', 'from': 'peer-a', 'text': 'hola bob', 'ts': 0})),
    );
    expect(delivered, isTrue);

    final chatMsg = await chatReceived.future.timeout(const Duration(seconds: 30));
    expect(chatMsg['text'], 'hola bob');

    // --- Real chunked file transfer (offer/accept/stream/done) ---
    tmpDir = await Directory.systemTemp.createTemp('linkchat_test_');
    final srcFile = File('${tmpDir.path}/hello.bin');
    await srcFile.writeAsBytes(List.generate(200000, (i) => i % 256));

    // Subscribe to both "done" events *before* triggering the transfer:
    // ftA/ftB.updates are broadcast streams, so a subscriber that starts
    // listening only after the transfer is already underway can miss an
    // event that fired earlier (broadcast streams don't replay history).
    final offerReceived = Completer<FileTransfer>();
    final doneOnA = Completer<FileTransfer>();
    final doneOnB = Completer<FileTransfer>();
    ftB.updates.listen((t) {
      if (t.direction == TransferDirection.receive &&
          t.status == TransferStatus.offering &&
          !offerReceived.isCompleted) {
        offerReceived.complete(t);
      }
      if (t.status == TransferStatus.done && !doneOnB.isCompleted) {
        doneOnB.complete(t);
      }
    });
    ftA.updates.listen((t) {
      if (t.status == TransferStatus.done && !doneOnA.isCompleted) {
        doneOnA.complete(t);
      }
    });

    final sidFuture = ftA.offerFile(peerB, srcFile);
    final offer = await offerReceived.future.timeout(const Duration(seconds: 30));
    await ftB.respondToOffer(offer.sid, true);

    final sid = await sidFuture;
    expect(sid, isNotNull);

    await doneOnA.future.timeout(const Duration(seconds: 45));
    final doneRx = await doneOnB.future.timeout(const Duration(seconds: 45));

    final receivedBytes = await File(doneRx.localPath!).readAsBytes();
    final sentBytes = await srcFile.readAsBytes();
    expect(receivedBytes, sentBytes);
  }, timeout: const Timeout(Duration(seconds: 180)));
}
