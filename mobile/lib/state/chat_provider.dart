import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:uuid/uuid.dart';

import '../models/chat_message.dart';
import '../models/peer.dart';
import '../network/connection_manager.dart';
import '../network/protocol.dart';
import '../services/chat_repository.dart';
import '../services/identity_service.dart';

/// Central hub for 1:1 chat: sends/receives [InnerType.chat] frames, persists
/// history via [ChatRepository], and tracks per-message delivery status.
class ChatProvider extends ChangeNotifier {
  final ConnectionManager connections;
  final ChatRepository repo;
  final IdentityService identity;

  final Map<String, List<ChatMessage>> _byPeer = {};
  StreamSubscription? _sub;

  ChatProvider({
    required this.connections,
    required this.repo,
    required this.identity,
  }) {
    _sub = connections.inboundFrames.listen(_onFrame);
  }

  List<ChatMessage> messagesFor(String peerId) => _byPeer[peerId] ?? const [];

  Future<void> loadHistory(String peerId) async {
    if (_byPeer.containsKey(peerId)) return;
    _byPeer[peerId] = await repo.history(peerId);
    notifyListeners();
  }

  Future<void> sendMessage(Peer peer, String text) async {
    final id = const Uuid().v4().substring(0, 8);
    final msg = ChatMessage(
      id: id,
      peerId: peer.id,
      text: text,
      ts: DateTime.now(),
      isMine: true,
      status: MessageStatus.sending,
    );
    _append(msg);
    await repo.insert(msg);

    final delivered = await connections.send(
      peer,
      InnerType.chat,
      utf8.encode(jsonEncode({
        'id': id,
        'from': identity.id,
        'text': text,
        'ts': msg.ts.millisecondsSinceEpoch,
      })),
    );
    await _setStatus(peer.id, id, delivered ? MessageStatus.sent : MessageStatus.failed);
  }

  Future<void> sendToAll(Iterable<Peer> peers, String text) async {
    for (final peer in peers) {
      await sendMessage(peer, text);
    }
  }

  void _onFrame(InboundFrame inbound) {
    final (peerId, frame) = inbound;

    if (frame.type == InnerType.chat) {
      try {
        final map = jsonDecode(utf8.decode(frame.payload)) as Map<String, dynamic>;
        final id = map['id'] as String;
        final text = map['text'] as String;
        final tsMs = map['ts'] as int;
        final msg = ChatMessage(
          id: id,
          peerId: peerId,
          text: text,
          ts: DateTime.fromMillisecondsSinceEpoch(tsMs),
          isMine: false,
          status: MessageStatus.delivered,
        );
        _append(msg);
        repo.insert(msg);
        connections.sendToPeerId(peerId, InnerType.ack, utf8.encode(jsonEncode({'id': id})));
      } catch (_) {
        // malformed frame -- ignore
      }
      return;
    }

    if (frame.type == InnerType.ack) {
      try {
        final map = jsonDecode(utf8.decode(frame.payload)) as Map<String, dynamic>;
        final id = map['id'] as String;
        _setStatus(peerId, id, MessageStatus.delivered);
      } catch (_) {
        // ignore
      }
    }
  }

  void _append(ChatMessage msg) {
    _byPeer.putIfAbsent(msg.peerId, () => []).add(msg);
    notifyListeners();
  }

  Future<void> _setStatus(String peerId, String id, MessageStatus status) async {
    final list = _byPeer[peerId];
    if (list != null) {
      final idx = list.indexWhere((m) => m.id == id);
      if (idx >= 0) {
        list[idx] = list[idx].copyWith(status: status);
        notifyListeners();
      }
    }
    await repo.updateStatus(id, status);
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }
}
