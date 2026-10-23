import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/foundation.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'screens/home_screen.dart';
import 'screens/login_screen.dart';
import 'theme/terminal_theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  const url = String.fromEnvironment('SUPABASE_URL');
  const key = String.fromEnvironment('SUPABASE_PUBLISHABLE_KEY');

  if (url.isEmpty || key.isEmpty) {
    throw StateError('Missing Supabase configuration');
  }

  // Fail closed: publicly distributed builds must not connect over HTTP
  // or accidentally point to the developer's localhost backend.
  const apiBaseUrl = String.fromEnvironment('API_BASE_URL');
  if (kReleaseMode) {
    final apiUri = Uri.tryParse(apiBaseUrl);
    if (apiUri == null ||
        apiUri.scheme != 'https' ||
        apiUri.host.isEmpty ||
        ['localhost', '127.0.0.1', '10.0.2.2'].contains(apiUri.host)) {
      throw StateError('Release builds require a public HTTPS API_BASE_URL');
    }
    if (!url.startsWith('https://')) {
      throw StateError('Release builds require an HTTPS SUPABASE_URL');
    }
  }

  await Supabase.initialize(url: url, publishableKey: key);

  runApp(const SpendWiseApp());
}

class SpendWiseApp extends StatelessWidget {
  const SpendWiseApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'SpendWise AI',
      debugShowCheckedModeBanner: false,
      theme: createTerminalTheme(),
      builder: (context, child) => Stack(
        fit: StackFit.expand,
        children: [
          child ?? const SizedBox.shrink(),
          const Positioned.fill(child: TerminalAtmosphere()),
        ],
      ),
      home: const AuthGate(),
    );
  }
}

class AuthGate extends StatefulWidget {
  const AuthGate({super.key});

  @override
  State<AuthGate> createState() => _AuthGateState();
}

class _AuthGateState extends State<AuthGate> {
  StreamSubscription<AuthState>? _subscription;
  late bool _signedIn;

  @override
  void initState() {
    super.initState();

    final auth = Supabase.instance.client.auth;
    _signedIn = auth.currentSession != null;

    _subscription = auth.onAuthStateChange.listen(
      (event) {
        if (!mounted) return;

        setState(() {
          _signedIn = event.session != null;
        });
      },
      onError: (Object error, StackTrace stack) {
        debugPrint('Authentication state error');
      },
    );
  }

  @override
  void dispose() {
    _subscription?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return _signedIn ? const HomeScreen() : const LoginScreen();
  }
}
