import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:uuid/uuid.dart';

import '../models/file_transfer.dart';
import '../models/peer.dart';
import '../network/connection_manager.dart';
import '../network/protocol.dart';

/// Offer/accept/reject handshake + chunked streaming for file transfers.
///
/// Unlike the raw-socket version's FTv2 (which needed a sliding window and
/// per-chunk ACK/retry because Ethernet frames can be lost or reordered),
/// this runs over an already-reliable TCP [PeerConnection]: chunks are just
/// written in order with no sequence numbers, retries, or CRC -- the OS
/// guarantees ordered, complete delivery or tells us the socket failed.
class FileTransferService {
  static const int chunkSize = 64 * 1024;

  final ConnectionManager connections;
  final Map<String, FileTransfer> _transfers = {};
  final Map<String, Completer<bool>> _pendingOffers = {};
  final Map<String, IOSink> _openSinks = {};
  final StreamController<FileTransfer> _updates =
      StreamController<FileTransfer>.broadcast();

  StreamSubscription? _sub;

  FileTransferService({required this.connections}) {
    _sub = connections.inboundFrames.listen(_onFrame);
  }

  Stream<FileTransfer> get updates => _updates.stream;
  FileTransfer? transfer(String sid) => _transfers[sid];

  /// Sends [file] to [peer]: offers it, waits (up to 30s) for accept/reject,
  /// then streams it if accepted. Returns the session id, or null if the
  /// offer couldn't even be delivered.
  Future<String?> offerFile(Peer peer, File file) async {
    final sid = const Uuid().v4().substring(0, 12);
    final size = await file.length();
    final name = p.basename(file.path);

    _setTransfer(FileTransfer(
      sid: sid,
      peerId: peer.id,
      fileName: name,
      size: size,
      direction: TransferDirection.send,
      bytesDone: 0,
      status: TransferStatus.offering,
    ));

    final delivered = await connections.send(
      peer,
      InnerType.fileOffer,
      utf8.encode(jsonEncode({'sid': sid, 'name': name, 'size': size})),
    );
    if (!delivered) {
      _setStatus(sid, TransferStatus.failed);
      return null;
    }

    final completer = Completer<bool>();
    _pendingOffers[sid] = completer;
    bool accepted;
    try {
      accepted = await completer.future.timeout(const Duration(seconds: 30));
    } catch (_) {
      accepted = false;
    }
    _pendingOffers.remove(sid);

    if (!accepted) {
      _setStatus(sid, TransferStatus.rejected);
      return sid;
    }

    _setStatus(sid, TransferStatus.transferring);
    unawaited(_streamFile(sid, peer, file));
    return sid;
  }

  Future<void> _streamFile(String sid, Peer peer, File file) async {
    final raf = await file.open();
    final sidBytes = utf8.encode(sid);
    int sent = 0;
    try {
      while (true) {
        final chunk = await raf.read(chunkSize);
        if (chunk.isEmpty) break;
        final payload = <int>[sidBytes.length, ...sidBytes, ...chunk];
        final ok = await connections.send(peer, InnerType.fileChunk, payload);
        if (!ok) throw const SocketException('connection lost mid-transfer');
        sent += chunk.length;
        _bumpProgress(sid, sent);
      }
      await connections.send(
        peer,
        InnerType.fileDone,
        utf8.encode(jsonEncode({'sid': sid})),
      );
      _setStatus(sid, TransferStatus.done);
    } catch (_) {
      _setStatus(sid, TransferStatus.failed);
    } finally {
      await raf.close();
    }
  }

  /// Accepts or rejects a transfer that was offered to us.
  Future<void> respondToOffer(String sid, bool accept) async {
    final t = _transfers[sid];
    if (t == null) return;

    if (!accept) {
      _setStatus(sid, TransferStatus.rejected);
      await connections.sendToPeerId(
          t.peerId, InnerType.fileReject, utf8.encode(jsonEncode({'sid': sid})));
      return;
    }

    final dir = await getApplicationDocumentsDirectory();
    final inbox = Directory(p.join(dir.path, 'inbox'));
    await inbox.create(recursive: true);
    final target = File(p.join(inbox.path, t.fileName));
    _openSinks[sid] = target.openWrite();

    _setTransfer(t.copyWith(status: TransferStatus.transferring, localPath: target.path));
    await connections.sendToPeerId(
        t.peerId, InnerType.fileAccept, utf8.encode(jsonEncode({'sid': sid})));
  }

  void _onFrame(InboundFrame inbound) {
    final (peerId, frame) = inbound;
    switch (frame.type) {
      case InnerType.fileOffer:
        _handleOffer(peerId, frame.payload);
        break;
      case InnerType.fileAccept:
        _resolveOffer(frame.payload, true);
        break;
      case InnerType.fileReject:
        _resolveOffer(frame.payload, false);
        break;
      case InnerType.fileChunk:
        _handleChunk(frame.payload);
        break;
      case InnerType.fileDone:
        _handleDone(frame.payload);
        break;
    }
  }

  void _handleOffer(String peerId, List<int> payload) {
    try {
      final map = jsonDecode(utf8.decode(payload)) as Map<String, dynamic>;
      final sid = map['sid'] as String;
      final name = map['name'] as String;
      final size = map['size'] as int;
      _setTransfer(FileTransfer(
        sid: sid,
        peerId: peerId,
        fileName: name,
        size: size,
        direction: TransferDirection.receive,
        bytesDone: 0,
        status: TransferStatus.offering,
      ));
    } catch (_) {
      // malformed offer -- ignore
    }
  }

  void _resolveOffer(List<int> payload, bool accepted) {
    try {
      final map = jsonDecode(utf8.decode(payload)) as Map<String, dynamic>;
      final sid = map['sid'] as String;
      _pendingOffers[sid]?.complete(accepted);
    } catch (_) {
      // ignore
    }
  }

  void _handleChunk(List<int> payload) {
    if (payload.isEmpty) return;
    final sidLen = payload[0];
    if (payload.length < 1 + sidLen) return;
    final sid = utf8.decode(payload.sublist(1, 1 + sidLen));
    final chunk = payload.sublist(1 + sidLen);

    final sink = _openSinks[sid];
    final t = _transfers[sid];
    if (sink == null || t == null) return;

    sink.add(chunk);
    _bumpProgress(sid, t.bytesDone + chunk.length);
  }

  void _handleDone(List<int> payload) {
    try {
      final map = jsonDecode(utf8.decode(payload)) as Map<String, dynamic>;
      final sid = map['sid'] as String;
      final sink = _openSinks.remove(sid);
      final t = _transfers[sid];
      if (sink != null) {
        sink.close();
      }
      if (t != null) {
        final ok = t.bytesDone >= t.size;
        _setStatus(sid, ok ? TransferStatus.done : TransferStatus.failed);
      }
    } catch (_) {
      // ignore
    }
  }

  void _bumpProgress(String sid, int bytesDone) {
    final t = _transfers[sid];
    if (t == null) return;
    _setTransfer(t.copyWith(bytesDone: bytesDone));
  }

  void _setStatus(String sid, TransferStatus status) {
    final t = _transfers[sid];
    if (t == null) return;
    _setTransfer(t.copyWith(status: status));
  }

  void _setTransfer(FileTransfer t) {
    _transfers[t.sid] = t;
    if (!_updates.isClosed) _updates.add(t);
  }

  void dispose() {
    _sub?.cancel();
    for (final sink in _openSinks.values) {
      sink.close();
    }
    _openSinks.clear();
    _updates.close();
  }
}
