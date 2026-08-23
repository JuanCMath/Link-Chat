import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';

import '../services/identity_service.dart';
import 'crypto_session.dart';
import 'framing.dart';
import 'protocol.dart';

/// One TCP connection to a single peer: performs the X25519 handshake, then
/// exposes a stream of decrypted application frames and a method to send
/// them. Chat messages and file chunks are multiplexed over the same
/// connection, distinguished by [InnerType].
class PeerConnection {
  final Socket socket;
  final IdentityService identity;
  void Function()? onClosed;

  final FrameDecoder _decoder = FrameDecoder();
  final Completer<void> _handshakeDone = Completer<void>();
  final StreamController<Frame> _innerController =
      StreamController<Frame>.broadcast();

  late final SimpleKeyPair _localKeyPair;
  CryptoSession? _crypto;
  bool _closed = false;

  String? _remotePeerId;
  String? _remoteName;

  PeerConnection(this.socket, this.identity);

  String get remotePeerId => _remotePeerId!;
  String get remoteName => _remoteName!;
  Stream<Frame> get inner => _innerController.stream;
  Future<void> get handshakeDone => _handshakeDone.future;

  Future<void> start() async {
    socket.listen(
      _decoder.add,
      onDone: _handleClose,
      onError: (Object _, StackTrace __) => _handleClose(),
      cancelOnError: true,
    );
    // asyncMap (not listen) so a burst of frames delivered in one TCP read
    // is still handled one at a time, in order -- otherwise concurrent
    // decrypts of back-to-back frames can finish out of order (e.g. a
    // FILE_DONE control frame overtaking the last FILE_CHUNK before it).
    _decoder.frames.asyncMap(_onOuterFrame).listen((_) {});

    _localKeyPair = await CryptoSession.generateEphemeralKeyPair();
    final pubBytes = await CryptoSession.publicKeyBytes(_localKeyPair);
    final hello = jsonEncode({
      'id': identity.id,
      'name': identity.name,
      'pub': base64Encode(pubBytes),
    });
    _writeOuter(OuterType.helloKey, utf8.encode(hello));
  }

  Future<void> _onOuterFrame(Frame frame) async {
    if (frame.type == OuterType.helloKey) {
      if (_handshakeDone.isCompleted) return;
      try {
        final map = jsonDecode(utf8.decode(frame.payload)) as Map<String, dynamic>;
        _remotePeerId = map['id'] as String;
        _remoteName = map['name'] as String;
        final remotePub = base64Decode(map['pub'] as String);
        _crypto = await CryptoSession.deriveFromHandshake(
          localKeyPair: _localKeyPair,
          remotePublicKeyBytes: remotePub,
        );
        _handshakeDone.complete();
      } catch (_) {
        await close();
      }
      return;
    }

    if (frame.type == OuterType.secure) {
      final crypto = _crypto;
      if (crypto == null) return; // secure frame before handshake -- drop
      try {
        final clear = await crypto.decrypt(frame.payload);
        if (clear.isEmpty) return;
        final innerType = clear[0];
        final innerPayload = Uint8List.fromList(clear.sublist(1));
        if (!_innerController.isClosed) {
          _innerController.add(Frame(innerType, innerPayload));
        }
      } catch (_) {
        // Authentication failure or corrupt frame -- drop silently.
      }
    }
  }

  Future<void> sendInner(int innerType, List<int> innerPayload) async {
    await _handshakeDone.future;
    final crypto = _crypto;
    if (crypto == null || _closed) return;
    final plain = <int>[innerType, ...innerPayload];
    final packed = await crypto.encrypt(plain);
    _writeOuter(OuterType.secure, packed);
    await socket.flush();
  }

  void _writeOuter(int type, List<int> payload) {
    if (_closed) return;
    try {
      socket.add(FrameCodec.encode(type, payload));
    } catch (_) {
      _handleClose();
    }
  }

  void _handleClose() {
    if (_closed) return;
    _closed = true;
    _decoder.close();
    if (!_innerController.isClosed) _innerController.close();
    onClosed?.call();
  }

  Future<void> close() async {
    _handleClose();
    try {
      await socket.close();
    } catch (_) {
      // already closed
    }
  }
}
