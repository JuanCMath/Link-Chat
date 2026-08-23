import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

/// Persistent local identity: a stable peer id (survives reinstalls of the
/// same app data) plus an editable display name.
///
/// IP addresses change with DHCP so the peer id -- not the address -- is
/// what identifies "this device" to others on the network. Extends
/// [ChangeNotifier] purely so the app bar can reflect a renamed device
/// without plumbing a separate settings stream.
class IdentityService extends ChangeNotifier {
  static const _kIdKey = 'linkchat.peer_id';
  static const _kNameKey = 'linkchat.display_name';

  SharedPreferences? _prefs;
  late String id;
  late String name;

  IdentityService();

  /// Bypasses SharedPreferences entirely -- for tests that need two distinct
  /// in-process identities (a mocked prefs store is shared/global across a
  /// single test process, so it can't represent two separate devices).
  IdentityService.fixed(this.id, this.name);

  Future<void> load() async {
    final prefs = await SharedPreferences.getInstance();
    _prefs = prefs;

    id = prefs.getString(_kIdKey) ?? const Uuid().v4();
    await prefs.setString(_kIdKey, id);

    name = prefs.getString(_kNameKey) ?? _defaultName();
    await prefs.setString(_kNameKey, name);
  }

  Future<void> setName(String newName) async {
    final trimmed = newName.trim();
    if (trimmed.isEmpty) return;
    name = trimmed;
    await _prefs?.setString(_kNameKey, name);
    notifyListeners();
  }

  String _defaultName() {
    final suffix = const Uuid().v4().substring(0, 4);
    return 'LinkChat-$suffix';
  }
}
