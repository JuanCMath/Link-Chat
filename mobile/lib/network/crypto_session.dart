import 'dart:convert';
import 'dart:typed_data';

import 'package:cryptography/cryptography.dart';

/// Per-connection end-to-end encryption.
///
/// Each TCP connection performs an X25519 ephemeral key exchange (the
/// `HELLO_KEY` control frame in [PeerConnection]) and derives a ChaCha20-
/// Poly1305 session key via HKDF from the shared secret. This replaces the
/// original project's single global pre-shared key with a fresh key per
/// connection, negotiated locally on the LAN -- a real security upgrade,
/// still built on the same ChaCha20-Poly1305 AEAD primitive.
class CryptoSession {
  static final X25519 _x25519 = X25519();
  static final Hkdf _hkdf = Hkdf(hmac: Hmac.sha256(), outputLength: 32);
  static final Chacha20 _aead = Chacha20.poly1305Aead();

  final SecretKey _sessionKey;

  CryptoSession._(this._sessionKey);

  static Future<SimpleKeyPair> generateEphemeralKeyPair() =>
      _x25519.newKeyPair();

  static Future<Uint8List> publicKeyBytes(SimpleKeyPair keyPair) async {
    final pub = await keyPair.extractPublicKey();
    return Uint8List.fromList(pub.bytes);
  }

  static Future<CryptoSession> deriveFromHandshake({
    required SimpleKeyPair localKeyPair,
    required List<int> remotePublicKeyBytes,
  }) async {
    final remotePublicKey =
        SimplePublicKey(remotePublicKeyBytes, type: KeyPairType.x25519);
    final sharedSecret = await _x25519.sharedSecretKey(
      keyPair: localKeyPair,
      remotePublicKey: remotePublicKey,
    );
    final sessionKey = await _hkdf.deriveKey(
      secretKey: sharedSecret,
      info: utf8.encode('linkchat-mobile-session-v1'),
    );
    return CryptoSession._(sessionKey);
  }

  /// Encrypts [plaintext], returning `nonce(12) + cipherText + mac(16)`.
  Future<Uint8List> encrypt(List<int> plaintext) async {
    final box = await _aead.encrypt(plaintext, secretKey: _sessionKey);
    return Uint8List.fromList([...box.nonce, ...box.cipherText, ...box.mac.bytes]);
  }

  /// Decrypts a payload produced by [encrypt].
  Future<Uint8List> decrypt(Uint8List packed) async {
    const nonceLen = 12;
    const macLen = 16;
    if (packed.length < nonceLen + macLen) {
      throw const FormatException('encrypted payload too short');
    }
    final nonce = packed.sublist(0, nonceLen);
    final cipherText = packed.sublist(nonceLen, packed.length - macLen);
    final mac = Mac(packed.sublist(packed.length - macLen));
    final box = SecretBox(cipherText, nonce: nonce, mac: mac);
    final clear = await _aead.decrypt(box, secretKey: _sessionKey);
    return Uint8List.fromList(clear);
  }
}
