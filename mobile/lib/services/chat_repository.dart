import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:sqflite/sqflite.dart';

import '../models/chat_message.dart';

/// Local persistence for chat history, keyed by conversation partner
/// (`peer_id`). Peers are identified by their stable UUID (see
/// [IdentityService]), not by IP, so history survives address changes.
class ChatRepository {
  Database? _db;

  Future<void> open() async {
    if (_db != null) return;
    final dir = await getApplicationDocumentsDirectory();
    final path = p.join(dir.path, 'linkchat_messages.db');
    _db = await openDatabase(
      path,
      version: 1,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE messages (
            id TEXT PRIMARY KEY,
            peer_id TEXT NOT NULL,
            text TEXT NOT NULL,
            ts INTEGER NOT NULL,
            is_mine INTEGER NOT NULL,
            status TEXT NOT NULL
          )
        ''');
        await db.execute(
            'CREATE INDEX idx_messages_peer_ts ON messages(peer_id, ts)');
      },
    );
  }

  Future<void> insert(ChatMessage message) async {
    await _db!.insert('messages', message.toDb(),
        conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<void> updateStatus(String id, MessageStatus status) async {
    await _db!.update('messages', {'status': status.name},
        where: 'id = ?', whereArgs: [id]);
  }

  Future<List<ChatMessage>> history(String peerId, {int limit = 500}) async {
    final rows = await _db!.query(
      'messages',
      where: 'peer_id = ?',
      whereArgs: [peerId],
      orderBy: 'ts ASC',
      limit: limit,
    );
    return rows.map(ChatMessage.fromDb).toList();
  }
}
