import 'dart:async';

import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'screens/home_screen.dart';
import 'screens/login_screen.dart';
import 'offline/app.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  // The public app has no server, account or billable inference dependency.
  const useLegacyBackend = bool.fromEnvironment('ENABLE_LEGACY_BACKEND');
  if (!useLegacyBackend) {
    runApp(const OfflineSpendWiseApp());
    return;
  }

  const url = String.fromEnvironment('SUPABASE_URL');
  const key = String.fromEnvironment('SUPABASE_PUBLISHABLE_KEY');

  if (url.isEmpty || key.isEmpty) {
    throw StateError('Missing Supabase configuration');
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
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.teal),
        useMaterial3: true,
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
