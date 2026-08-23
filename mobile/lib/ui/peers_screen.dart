import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../models/peer.dart';
import '../services/identity_service.dart';
import '../state/chat_provider.dart';
import '../state/peers_provider.dart';
import 'chat_screen.dart';
import 'settings_screen.dart';

class PeersScreen extends StatelessWidget {
  const PeersScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final peers = context.watch<PeersProvider>().peers;
    final identity = context.watch<IdentityService>();

    return Scaffold(
      appBar: AppBar(
        title: Text('Link-Chat · ${identity.name}'),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings),
            onPressed: () => Navigator.push(
              context,
              MaterialPageRoute(builder: (_) => const SettingsScreen()),
            ),
          ),
        ],
      ),
      body: peers.isEmpty
          ? const Center(child: Text('Buscando dispositivos en la red...'))
          : ListView.separated(
              itemCount: peers.length,
              separatorBuilder: (_, __) => const Divider(height: 1),
              itemBuilder: (context, i) {
                final peer = peers[i];
                return ListTile(
                  leading: const CircleAvatar(child: Icon(Icons.smartphone)),
                  title: Text(peer.name),
                  subtitle: Text('${peer.address.address}:${peer.tcpPort}'),
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute(builder: (_) => ChatScreen(peerId: peer.id)),
                  ),
                );
              },
            ),
      floatingActionButton: peers.isEmpty
          ? null
          : FloatingActionButton.extended(
              icon: const Icon(Icons.campaign),
              label: const Text('Enviar a todos'),
              onPressed: () => _showBroadcastDialog(context, peers),
            ),
    );
  }

  Future<void> _showBroadcastDialog(BuildContext context, List<Peer> peers) async {
    final controller = TextEditingController();
    final chat = context.read<ChatProvider>();

    final text = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Mensaje a todos'),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: const InputDecoration(hintText: 'Escribe un mensaje...'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text),
            child: const Text('Enviar'),
          ),
        ],
      ),
    );

    if (text != null && text.trim().isNotEmpty) {
      await chat.sendToAll(peers, text.trim());
    }
  }
}
