enum MessageStatus { sending, sent, delivered, failed }

/// A single chat message exchanged with one peer (1:1 conversation).
class ChatMessage {
  final String id;
  final String peerId;
  final String text;
  final DateTime ts;
  final bool isMine;
  final MessageStatus status;

  const ChatMessage({
    required this.id,
    required this.peerId,
    required this.text,
    required this.ts,
    required this.isMine,
    required this.status,
  });

  ChatMessage copyWith({MessageStatus? status}) => ChatMessage(
        id: id,
        peerId: peerId,
        text: text,
        ts: ts,
        isMine: isMine,
        status: status ?? this.status,
      );

  Map<String, Object?> toDb() => {
        'id': id,
        'peer_id': peerId,
        'text': text,
        'ts': ts.millisecondsSinceEpoch,
        'is_mine': isMine ? 1 : 0,
        'status': status.name,
      };

  static ChatMessage fromDb(Map<String, Object?> row) => ChatMessage(
        id: row['id'] as String,
        peerId: row['peer_id'] as String,
        text: row['text'] as String,
        ts: DateTime.fromMillisecondsSinceEpoch(row['ts'] as int),
        isMine: (row['is_mine'] as int) == 1,
        status: MessageStatus.values.byName(row['status'] as String),
      );
}
