import 'dart:async';
import 'dart:convert';
import 'dart:io';

import '../models/peer.dart';
import '../services/identity_service.dart';

/// Announces this device on the local network via UDP broadcast and keeps a
/// live registry of the peers heard from. Mirrors the beacon idea from the
/// original raw-socket LinkChat, but over IP: broadcast "hello" datagrams
/// instead of Ethernet frames, since phones cannot open AF_PACKET sockets.
class DiscoveryService {
  static const int discoveryPort = 47500;
  static const Duration beaconInterval = Duration(seconds: 3);
  static const Duration pruneInterval = Duration(seconds: 5);

  final IdentityService identity;
  final int Function() tcpPortProvider;

  RawDatagramSocket? _socket;
  Timer? _beaconTimer;
  Timer? _pruneTimer;
  final Map<String, Peer> _peers = {};
  final StreamController<List<Peer>> _controller =
      StreamController<List<Peer>>.broadcast();

  DiscoveryService({required this.identity, required this.tcpPortProvider});

  Stream<List<Peer>> get peers => _controller.stream;
  List<Peer> get currentPeers => _peers.values.toList(growable: false);

  Future<void> start() async {
    if (_socket != null) return;
    _socket = await RawDatagramSocket.bind(
      InternetAddress.anyIPv4,
      discoveryPort,
      reuseAddress: true,
    );
    _socket!.broadcastEnabled = true;
    _socket!.listen(_onEvent);

    _beaconTimer = Timer.periodic(beaconInterval, (_) => sendBeacon());
    _pruneTimer = Timer.periodic(pruneInterval, (_) => _prune());
    sendBeacon();
  }

  void stop() {
    _beaconTimer?.cancel();
    _pruneTimer?.cancel();
    _beaconTimer = null;
    _pruneTimer = null;
    _socket?.close();
    _socket = null;
  }

  void sendBeacon() {
    final socket = _socket;
    if (socket == null) return;
    final payload = utf8.encode(jsonEncode({
      't': 'hello',
      'id': identity.id,
      'name': identity.name,
      'tcp': tcpPortProvider(),
    }));
    try {
      socket.send(payload, InternetAddress('255.255.255.255'), discoveryPort);
    } catch (_) {
      // Network unreachable (e.g. no WiFi) -- ignore, next tick retries.
    }
  }

  void _onEvent(RawSocketEvent event) {
    if (event != RawSocketEvent.read) return;
    final socket = _socket;
    if (socket == null) return;
    final datagram = socket.receive();
    if (datagram == null) return;

    try {
      final decoded = jsonDecode(utf8.decode(datagram.data));
      if (decoded is! Map<String, dynamic>) return;
      if (decoded['t'] != 'hello') return;

      final id = decoded['id'];
      final name = decoded['name'];
      final tcp = decoded['tcp'];
      if (id is! String || name is! String || tcp is! int) return;
      if (id == identity.id) return; // ignore our own beacon

      _peers[id] = Peer(
        id: id,
        name: name,
        address: datagram.address,
        tcpPort: tcp,
        lastSeen: DateTime.now(),
      );
      _controller.add(currentPeers);
    } catch (_) {
      // Malformed/foreign UDP packet on this port -- ignore.
    }
  }

  void _prune() {
    final before = _peers.length;
    _peers.removeWhere((_, peer) => peer.isStale);
    if (_peers.length != before) {
      _controller.add(currentPeers);
    }
  }

  void dispose() {
    stop();
    _controller.close();
  }
}
