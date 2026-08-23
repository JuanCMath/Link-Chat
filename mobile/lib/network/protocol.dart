/// Outer wire frame types (visible before decryption).
class OuterType {
  static const int helloKey = 0x01; // plaintext handshake
  static const int secure = 0x02; // ciphertext wrapping an InnerType frame
}

/// Inner (application) frame types, only ever seen after decryption.
class InnerType {
  static const int chat = 0x10;
  static const int fileOffer = 0x11;
  static const int fileAccept = 0x12;
  static const int fileReject = 0x13;
  static const int fileChunk = 0x14;
  static const int fileDone = 0x15;
  static const int ack = 0x16;
}
