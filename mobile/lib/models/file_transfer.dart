enum TransferDirection { send, receive }

enum TransferStatus { offering, accepted, rejected, transferring, done, failed }

/// State of a single file transfer session identified by [sid].
class FileTransfer {
  final String sid;
  final String peerId;
  final String fileName;
  final int size;
  final TransferDirection direction;
  final int bytesDone;
  final TransferStatus status;
  final String? localPath;

  const FileTransfer({
    required this.sid,
    required this.peerId,
    required this.fileName,
    required this.size,
    required this.direction,
    required this.bytesDone,
    required this.status,
    this.localPath,
  });

  double get progress => size == 0 ? 0 : bytesDone / size;

  FileTransfer copyWith({
    int? bytesDone,
    TransferStatus? status,
    String? localPath,
  }) {
    return FileTransfer(
      sid: sid,
      peerId: peerId,
      fileName: fileName,
      size: size,
      direction: direction,
      bytesDone: bytesDone ?? this.bytesDone,
      status: status ?? this.status,
      localPath: localPath ?? this.localPath,
    );
  }
}
