import 'dart:async';
import 'dart:io';

import '../models/peer.dart';
import '../services/identity_service.dart';
import 'framing.dart';
import 'peer_connection.dart';

/// A decrypted inner frame together with the peer id that sent it.
typedef InboundFrame = (String peerId, Frame frame);

/// Owns the incoming TCP listener and the pool of outgoing/incoming
/// [PeerConnection]s (one per remote peer id, reused across messages and
/// file transfers). Replaces the RX/TX/Dispatch thread trio from the
/// raw-socket version -- Dart's event loop plays that role here.
class ConnectionManager {
  final IdentityService identity;
  ServerSocket? _server;
  final Map<String, PeerConnection> _connections = {};
  final StreamController<InboundFrame> _inbound =
      StreamController<InboundFrame>.broadcast();

  ConnectionManager({required this.identity});

  Stream<InboundFrame> get inboundFrames => _inbound.stream;

  /// Port other peers should dial to reach us. 0 until [start] completes.
  int get tcpPort => _server?.port ?? 0;

  Future<void> start() async {
    if (_server != null) return;
    _server = await ServerSocket.bind(InternetAddress.anyIPv4, 0);
    _server!.listen(_onIncoming);
  }

  Future<void> stop() async {
    for (final conn in _connections.values.toList()) {
      await conn.close();
    }
    _connections.clear();
    await _server?.close();
    _server = null;
  }

  void _onIncoming(Socket socket) {
    final conn = PeerConnection(socket, identity);
    conn.start().catchError((_) => conn.close());
    conn.handshakeDone.then((_) => _register(conn)).catchError((_) {
      conn.close();
    });
  }

  void _register(PeerConnection conn) {
    final existing = _connections[conn.remotePeerId];
    if (existing != null && !identical(existing, conn)) {
      existing.close();
    }
    _connections[conn.remotePeerId] = conn;
    conn.onClosed = () {
      if (identical(_connections[conn.remotePeerId], conn)) {
        _connections.remove(conn.remotePeerId);
      }
    };
    conn.inner.listen((frame) => _inbound.add((conn.remotePeerId, frame)));
  }

  /// Returns an established, handshaked connection to [peer], reusing one
  /// already open or dialing a new one. Returns null if the peer is
  /// unreachable.
  Future<PeerConnection?> getOrConnect(Peer peer) async {
    final existing = _connections[peer.id];
    if (existing != null) return existing;

    try {
      final socket = await Socket.connect(
        peer.address,
        peer.tcpPort,
        timeout: const Duration(seconds: 5),
      );
      final conn = PeerConnection(socket, identity);
      await conn.start();
      await conn.handshakeDone.timeout(const Duration(seconds: 5));
      _register(conn);
      return conn;
    } catch (_) {
      return null;
    }
  }

  Future<bool> send(Peer peer, int innerType, List<int> payload) async {
    final conn = await getOrConnect(peer);
    if (conn == null) return false;
    await conn.sendInner(innerType, payload);
    return true;
  }

  /// Sends on an already-open connection, without dialing. Used to reply to
  /// a peer that just sent us a frame (we don't need their address/port to
  /// answer on the same socket).
  Future<bool> sendToPeerId(String peerId, int innerType, List<int> payload) async {
    final conn = _connections[peerId];
    if (conn == null) return false;
    await conn.sendInner(innerType, payload);
    return true;
  }

  void dispose() {
    stop();
    _inbound.close();
  }
}
