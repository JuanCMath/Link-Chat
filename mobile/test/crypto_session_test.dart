import 'package:flutter_test/flutter_test.dart';
import 'package:linkchat_mobile/network/crypto_session.dart';

void main() {
  test('both sides of a handshake derive a key that lets them talk', () async {
    final aliceKp = await CryptoSession.generateEphemeralKeyPair();
    final bobKp = await CryptoSession.generateEphemeralKeyPair();
    final alicePub = await CryptoSession.publicKeyBytes(aliceKp);
    final bobPub = await CryptoSession.publicKeyBytes(bobKp);

    final aliceSession = await CryptoSession.deriveFromHandshake(
      localKeyPair: aliceKp,
      remotePublicKeyBytes: bobPub,
    );
    final bobSession = await CryptoSession.deriveFromHandshake(
      localKeyPair: bobKp,
      remotePublicKeyBytes: alicePub,
    );

    final packed = await aliceSession.encrypt('hola bob'.codeUnits);
    final clear = await bobSession.decrypt(packed);

    expect(String.fromCharCodes(clear), 'hola bob');
  });

  test('tampering with an encrypted payload fails authentication', () async {
    final aliceKp = await CryptoSession.generateEphemeralKeyPair();
    final bobKp = await CryptoSession.generateEphemeralKeyPair();
    final alicePub = await CryptoSession.publicKeyBytes(aliceKp);
    final bobPub = await CryptoSession.publicKeyBytes(bobKp);

    final aliceSession = await CryptoSession.deriveFromHandshake(
      localKeyPair: aliceKp,
      remotePublicKeyBytes: bobPub,
    );
    final bobSession = await CryptoSession.deriveFromHandshake(
      localKeyPair: bobKp,
      remotePublicKeyBytes: alicePub,
    );

    final packed = await aliceSession.encrypt('hola bob'.codeUnits);
    packed[packed.length - 1] ^= 0xFF; // flip a bit in the auth tag

    expect(() => bobSession.decrypt(packed), throwsA(anything));
  });

  test('a third party without the shared secret cannot decrypt', () async {
    final aliceKp = await CryptoSession.generateEphemeralKeyPair();
    final bobKp = await CryptoSession.generateEphemeralKeyPair();
    final eveKp = await CryptoSession.generateEphemeralKeyPair();
    final alicePub = await CryptoSession.publicKeyBytes(aliceKp);
    final bobPub = await CryptoSession.publicKeyBytes(bobKp);

    final aliceSession = await CryptoSession.deriveFromHandshake(
      localKeyPair: aliceKp,
      remotePublicKeyBytes: bobPub,
    );
    final eveSession = await CryptoSession.deriveFromHandshake(
      localKeyPair: eveKp,
      remotePublicKeyBytes: alicePub,
    );

    final packed = await aliceSession.encrypt('secreto'.codeUnits);

    expect(() => eveSession.decrypt(packed), throwsA(anything));
  });
}
