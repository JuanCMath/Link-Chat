import 'package:flutter/material.dart';
import 'package:network_info_plus/network_info_plus.dart';
import 'package:provider/provider.dart';

import '../network/connection_manager.dart';
import '../network/discovery_service.dart';
import '../services/identity_service.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _nameController;
  String? _localIp;
  bool _discoveryOn = true;

  @override
  void initState() {
    super.initState();
    _nameController =
        TextEditingController(text: context.read<IdentityService>().name);
    _loadLocalIp();
  }

  Future<void> _loadLocalIp() async {
    try {
      final ip = await NetworkInfo().getWifiIP();
      if (mounted) setState(() => _localIp = ip);
    } catch (_) {
      if (mounted) setState(() => _localIp = 'no disponible');
    }
  }

  Future<void> _saveName() async {
    await context.read<IdentityService>().setName(_nameController.text);
    if (!mounted) return;
    context.read<DiscoveryService>().sendBeacon();
    ScaffoldMessenger.of(context)
        .showSnackBar(const SnackBar(content: Text('Nombre actualizado')));
  }

  @override
  Widget build(BuildContext context) {
    final identity = context.read<IdentityService>();
    final connections = context.read<ConnectionManager>();
    final discovery = context.read<DiscoveryService>();

    return Scaffold(
      appBar: AppBar(title: const Text('Ajustes')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          TextField(
            controller: _nameController,
            decoration: const InputDecoration(labelText: 'Nombre visible'),
            onSubmitted: (_) => _saveName(),
          ),
          const SizedBox(height: 8),
          Align(
            alignment: Alignment.centerRight,
            child: FilledButton(onPressed: _saveName, child: const Text('Guardar')),
          ),
          const Divider(height: 32),
          SwitchListTile(
            title: const Text('Descubrimiento activo'),
            subtitle: const Text('Anunciarse en la red y detectar otros dispositivos'),
            value: _discoveryOn,
            onChanged: (value) {
              setState(() => _discoveryOn = value);
              if (value) {
                discovery.start();
              } else {
                discovery.stop();
              }
            },
          ),
          const Divider(height: 32),
          ListTile(
            title: const Text('IP local'),
            subtitle: Text(_localIp ?? 'Detectando...'),
          ),
          ListTile(
            title: const Text('Puerto TCP'),
            subtitle: Text('${connections.tcpPort}'),
          ),
          ListTile(
            title: const Text('ID de dispositivo'),
            subtitle: Text(identity.id),
          ),
        ],
      ),
    );
  }
}
