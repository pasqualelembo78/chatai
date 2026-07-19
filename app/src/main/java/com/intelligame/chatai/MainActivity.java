package com.intelligame.chatai;

import android.app.AlarmManager;
import android.app.PendingIntent;
import android.app.PictureInPictureParams;
import android.content.Context;
import android.content.Intent;
import android.content.pm.PackageInfo;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Rational;
import android.view.MenuItem;
import android.view.View;
import android.widget.FrameLayout;
import android.widget.TextView;
import android.widget.Toast;
import android.widget.VideoView;

import androidx.activity.OnBackPressedCallback;
import androidx.core.content.ContextCompat;

import com.google.android.material.badge.BadgeDrawable;
import com.google.android.material.progressindicator.LinearProgressIndicator;

import androidx.appcompat.app.AppCompatActivity;
import androidx.appcompat.app.AlertDialog;
import androidx.appcompat.app.AppCompatDelegate;
import androidx.core.view.GravityCompat;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowCompat;
import androidx.drawerlayout.widget.DrawerLayout;
import androidx.fragment.app.Fragment;
import androidx.fragment.app.FragmentTransaction;

import com.google.android.material.appbar.MaterialToolbar;
import com.google.android.material.bottomnavigation.BottomNavigationView;
import com.google.android.material.navigation.NavigationView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.File;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends AppCompatActivity {

    private BottomNavigationView navView;
    private View fragmentContainer;
    private DrawerLayout drawerLayout;
    private NavigationView navDrawer;
    private MaterialToolbar topAppBar;
    private AuthManager mAuth;
    private AdManager mAdManager;
    private ChatApplication app;
    private ExecutorService executor = new SafeExecutor();
    private Handler mainHandler = new Handler(Looper.getMainLooper());
    private int pendingInvitations = 0;

    private static final String PREFS_THEME = "chatai_theme";
    private static final String KEY_THEME_MODE = "night_mode";

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        app = (ChatApplication) getApplication();
        mAuth = app.getAuthManager();
        mAdManager = app.getAdManager();

        if (!mAuth.isLoggedIn()) {
            Intent intent = new Intent(this, LoginActivity.class);
            intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
            finish();
            return;
        }

        // Show app open ad on launch (if not premium)
        PremiumManager pm = app.getPremiumManager();
        if (pm == null || !pm.isPremium()) {
            mAdManager.showAppOpenIfReady(this);
        }

        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);

        setContentView(R.layout.activity_main);

        // Register OnBackPressedCallback for predictive back gesture support (API 33+)
        getOnBackPressedDispatcher().addCallback(this, new OnBackPressedCallback(true) {
            @Override
            public void handleOnBackPressed() {
                if (getSupportFragmentManager().getBackStackEntryCount() > 0) {
                    getSupportFragmentManager().popBackStackImmediate();
                    if (getSupportFragmentManager().getBackStackEntryCount() == 0) {
                        navView.setVisibility(View.VISIBLE);
                    }
                } else {
                    Fragment current = getSupportFragmentManager().findFragmentById(R.id.fragment_container);
                    if (current instanceof HomeFragment) {
                        ChatApplication app2 = (ChatApplication) getApplication();
                        PremiumManager pm2 = app2.getPremiumManager();
                        if (pm2 == null || !pm2.isPremium()) {
                            mAdManager.showInterstitialIfReady(MainActivity.this);
                        }
                        // Allow default back behavior (exit app)
                        setEnabled(false);
                        onBackPressed();
                    } else {
                        navView.setSelectedItemId(R.id.nav_home);
                    }
                }
            }
        });

        navView = findViewById(R.id.nav_view);
        fragmentContainer = findViewById(R.id.fragment_container);
        drawerLayout = findViewById(R.id.drawer_layout);
        navDrawer = findViewById(R.id.nav_drawer);
        topAppBar = findViewById(R.id.top_app_bar);

        // Banner persistente (una sola view, visibile su tutte le schermate)
        FrameLayout bannerAdContainer = findViewById(R.id.banner_ad_container);
        PremiumManager pmBanner = app.getPremiumManager();
        if (pmBanner == null || !pmBanner.isPremium()) {
            mAdManager.showBanner(this, bannerAdContainer);
        } else {
            bannerAdContainer.setVisibility(View.GONE);
        }

        topAppBar.setNavigationOnClickListener(v -> drawerLayout.openDrawer(GravityCompat.START));
        navDrawer.setNavigationItemSelectedListener(this::onDrawerItemSelected);

        View root = findViewById(R.id.coordinator);
        ViewCompat.setOnApplyWindowInsetsListener(root, (v, insets) -> {
            int sysBottom = insets.getInsets(WindowInsetsCompat.Type.systemBars()).bottom;
            // Only account for the keyboard when it is actually visible. Some OEMs report a
            // non-zero IME inset even with the keyboard closed, which would otherwise shrink
            // the fragment container to ~half the screen and leave empty space at the bottom.
            int imeBottom = insets.isVisible(WindowInsetsCompat.Type.ime())
                    ? insets.getInsets(WindowInsetsCompat.Type.ime()).bottom : 0;

            navView.setPadding(0, 0, 0, sysBottom);

            // La bottom navigation è già un view separata sotto il contenitore, quindi
            // non serve aggiungere il suo spazio come padding. Applichiamo il padding
            // inferiore SOLO quando la tastiera è aperta, altrimenti rimane una striscia
            // vuota in basso (i fragment Home/Categorie non riempiono tutto lo schermo).
            fragmentContainer.setPadding(0, 0, 0, imeBottom);

            return WindowInsetsCompat.CONSUMED;
        });

        navView.setOnItemSelectedListener(item -> {
            int itemId = item.getItemId();
            Fragment fragment = null;
            String tag = null;

            if (itemId == R.id.nav_home) {
                fragment = new HomeFragment();
                tag = "home";
            } else if (itemId == R.id.nav_chat) {
                fragment = new ChatListFragment();
                tag = "chat";
            } else if (itemId == R.id.nav_groups) {
                fragment = new GroupChatListFragment();
                tag = "groups";
            } else if (itemId == R.id.nav_categories) {
                fragment = new CategoriesFragment();
                tag = "categories";
            } else if (itemId == R.id.nav_create) {
                fragment = new CreateFragment();
                tag = "create";
            }

            if (fragment != null) {
                switchFragment(fragment, tag);
            }
            return true;
        });

        if (savedInstanceState == null) {
            getSupportFragmentManager().beginTransaction()
                .add(R.id.fragment_container, new HomeFragment(), "home")
                .commit();
        } else {
            Fragment current = getSupportFragmentManager().findFragmentById(R.id.fragment_container);
            int currentId = R.id.nav_home;
            if (current instanceof ChatListFragment) currentId = R.id.nav_chat;
            else if (current instanceof GroupChatListFragment) currentId = R.id.nav_groups;
            else if (current instanceof CategoriesFragment) currentId = R.id.nav_categories;
            else if (current instanceof CreateFragment) currentId = R.id.nav_create;
            navView.setSelectedItemId(currentId);
        }

        handleIntent(getIntent());
        checkPendingInvitations();
        scheduleMvcReminder();
    }

    private void scheduleMvcReminder() {
        try {
            AlarmManager am = (AlarmManager) getSystemService(ALARM_SERVICE);
            if (am == null) return;
            Intent intent = new Intent(this, MvcReminderReceiver.class);
            PendingIntent pi = PendingIntent.getBroadcast(this, 0, intent,
                    PendingIntent.FLAG_UPDATE_CURRENT | PendingIntent.FLAG_IMMUTABLE);

            // Promemoria giornaliero alle 9:00 (orario locale, ripetizione approssimativa).
            java.util.Calendar cal = java.util.Calendar.getInstance();
            cal.set(java.util.Calendar.HOUR_OF_DAY, 9);
            cal.set(java.util.Calendar.MINUTE, 0);
            cal.set(java.util.Calendar.SECOND, 0);
            cal.set(java.util.Calendar.MILLISECOND, 0);
            if (cal.getTimeInMillis() <= System.currentTimeMillis()) {
                cal.add(java.util.Calendar.DAY_OF_MONTH, 1);
            }

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                if (am.canScheduleExactAlarms()) {
                    am.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, cal.getTimeInMillis(),
                            pi);
                } else {
                    am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, cal.getTimeInMillis(), pi);
                }
            } else if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
                am.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP, cal.getTimeInMillis(), pi);
            } else {
                am.set(AlarmManager.RTC_WAKEUP, cal.getTimeInMillis(), pi);
            }

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
                if (ContextCompat.checkSelfPermission(this,
                        android.Manifest.permission.POST_NOTIFICATIONS)
                        != PackageManager.PERMISSION_GRANTED) {
                    requestPermissions(
                            new String[]{android.Manifest.permission.POST_NOTIFICATIONS}, 1001);
                }
            }
        } catch (Exception ignored) {}
    }

    @Override
    protected void onResume() {
        super.onResume();
        updateConsentMenu();
        checkPendingInvitations();
    }

    private void updateConsentMenu() {
        if (navView == null) return;
        MenuItem consentItem = navView.getMenu().findItem(R.id.nav_consent);
        if (consentItem != null) {
            consentItem.setVisible(((ChatApplication) getApplication()).getAdManager().isPrivacyOptionsRequired());
        }
    }

    private void confirmDeleteAccount() {
        new AlertDialog.Builder(this)
                .setTitle("Elimina account")
                .setMessage("Questa operazione cancellerà permanentemente il tuo account e tutti i dati associati (conversazioni, personaggi, MeVaCoin). L'operazione non è reversibile. Continuare?")
                .setCancelable(true)
                .setPositiveButton("Elimina", (d, w) -> deleteAccount())
                .setNegativeButton("Annulla", null)
                .show();
    }

    private void deleteAccount() {
        ChatApplication app = (ChatApplication) getApplication();
        String baseUrl = app.getPrefs().getServerUrl().replace("/chat", "");
        executor.execute(() -> {
            try {
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(
                        baseUrl + "/user/delete", "POST", "", 8000);
                mainHandler.post(() -> {
                    if (resp.statusCode == 200) {
                        clearAllLocalData();
                        Toast.makeText(MainActivity.this, "Account eliminato", Toast.LENGTH_SHORT).show();
                        Intent intent = new Intent(MainActivity.this, LoginActivity.class);
                        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_NEW_TASK);
                        startActivity(intent);
                        finish();
                    } else {
                        Toast.makeText(MainActivity.this, "Errore eliminazione (codice " + resp.statusCode + ")", Toast.LENGTH_SHORT).show();
                    }
                });
            } catch (Exception e) {
                mainHandler.post(() -> Toast.makeText(MainActivity.this,
                        "Errore eliminazione: " + e.getMessage(), Toast.LENGTH_SHORT).show());
            }
        });
    }

    /**
     * Completely clears all local user data including encrypted prefs, database, cache files.
     */
    private void clearAllLocalData() {
        try {
            app.getLocalDb().resetAll();
        } catch (Exception ignored) {}

        try {
            app.getPrefs().clearAll();
        } catch (Exception ignored) {}

        try {
            mAuth.clear();
        } catch (Exception ignored) {}

        try {
            getSharedPreferences("chatai_theme", Context.MODE_PRIVATE).edit().clear().apply();
        } catch (Exception ignored) {}

        try {
            File audioCache = new File(getCacheDir(), "audio");
            if (audioCache.exists()) deleteRecursive(audioCache);
        } catch (Exception ignored) {}

        try {
            File imageCache = new File(getCacheDir(), "images");
            if (imageCache.exists()) deleteRecursive(imageCache);
        } catch (Exception ignored) {}

        try {
            File[] cacheFiles = getCacheDir().listFiles();
            if (cacheFiles != null) {
                for (File f : cacheFiles) {
                    if (f.isFile() && (f.getName().endsWith(".tmp") || f.getName().endsWith(".wav"))) {
                        f.delete();
                    }
                }
            }
        } catch (Exception ignored) {}
    }

    private void deleteRecursive(File file) {
        if (file.isDirectory()) {
            File[] children = file.listFiles();
            if (children != null) {
                for (File child : children) {
                    deleteRecursive(child);
                }
            }
        }
        file.delete();
    }

    private void checkPendingInvitations() {
        executor.execute(() -> {
            try {
                ChatApplication app = (ChatApplication) getApplication();
                String baseUrl = app.getCurrentUrl();
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(
                    baseUrl + "/user/invitations", "GET", null, 5000);
                if (resp.statusCode == 200) {
                    JSONArray arr = new JSONArray(resp.body);
                    final int count = arr.length();
                    mainHandler.post(() -> {
                        pendingInvitations = count;
                        updateGroupsBadge();
                        if (count > 0 && getSupportFragmentManager().findFragmentByTag("groups") == null) {
                            showInvitationNotification(arr);
                        }
                    });
                }
            } catch (Exception ignored) {}
        });
    }

    private void updateGroupsBadge() {
        try {
            BadgeDrawable badge = navView.getOrCreateBadge(R.id.nav_groups);
            if (pendingInvitations > 0) {
                badge.setVisible(true);
                badge.setNumber(pendingInvitations);
            } else {
                badge.setVisible(false);
            }
        } catch (Exception ignored) {}
    }

    private void showInvitationNotification(JSONArray arr) {
        try {
            StringBuilder msg = new StringBuilder();
            msg.append("Hai ").append(arr.length()).append(" invito/i in attesa:");
            for (int i = 0; i < arr.length() && i < 3; i++) {
                JSONObject inv = arr.getJSONObject(i);
                msg.append("\n\n• ").append(inv.optString("chat_name"))
                   .append("\n  da ").append(inv.optString("inviter_id"));
            }
            if (arr.length() > 3) {
                msg.append("\n\n... e altri ").append(arr.length() - 3);
            }

            new androidx.appcompat.app.AlertDialog.Builder(this)
                .setTitle("Inviti di Gruppo")
                .setMessage(msg.toString())
                .setPositiveButton("Gestisci", (d, w) -> {
                    navView.setSelectedItemId(R.id.nav_groups);
                })
                .setNegativeButton("Più tardi", null)
                .show();
        } catch (Exception ignored) {}
    }

    @Override
    protected void onNewIntent(Intent intent) {
        super.onNewIntent(intent);
        handleIntent(intent);
    }

    private void handleIntent(Intent intent) {
        if (intent != null && intent.hasExtra("character_id")) {
            String characterId = intent.getStringExtra("character_id");
            String characterName = intent.getStringExtra("character_name");
            String initialMessage = intent.getStringExtra("initial_message");
            String avatarImage = intent.getStringExtra("character_avatar_image");
            String emoji = intent.getStringExtra("character_emoji");
            openChat(characterId, characterName, initialMessage, avatarImage, emoji);
        } else if (intent != null && intent.getBooleanExtra("open_earn", false)) {
            startActivity(new Intent(this, MvcEarnActivity.class));
        }
    }

    private void switchFragment(Fragment fragment, String tag) {
        FragmentTransaction transaction = getSupportFragmentManager().beginTransaction()
            .setCustomAnimations(android.R.anim.fade_in, android.R.anim.fade_out)
            .replace(R.id.fragment_container, fragment, tag);
        transaction.commit();
    }

    private boolean isNightMode() {
        int mode = getPreferences(MODE_PRIVATE).getInt(KEY_THEME_MODE, AppCompatDelegate.MODE_NIGHT_YES);
        return mode == AppCompatDelegate.MODE_NIGHT_YES;
    }

    private boolean onDrawerItemSelected(MenuItem item) {
        int id = item.getItemId();
        drawerLayout.closeDrawers();
        if (id == R.id.nav_profile) {
            switchFragment(new ProfileFragment(), "profile");
        } else if (id == R.id.nav_theme) {
            toggleNightMode();
        } else if (id == R.id.nav_guide) {
            showGuideDialog();
        } else if (id == R.id.nav_info) {
            showInfoDialog();
        } else if (id == R.id.nav_legal) {
            startActivity(new Intent(MainActivity.this, LegalActivity.class));
        } else if (id == R.id.nav_consent) {
            ((ChatApplication) getApplication()).getAdManager().showPrivacyOptionsForm(MainActivity.this, null);
        } else if (id == R.id.nav_delete_account) {
            confirmDeleteAccount();
        } else if (id == R.id.nav_playstore) {
            openPlayStore();
        } else if (id == R.id.nav_logout) {
            logout();
        }
        return true;
    }

    private void toggleNightMode() {
        boolean night = isNightMode();
        int newMode = night ? AppCompatDelegate.MODE_NIGHT_NO : AppCompatDelegate.MODE_NIGHT_YES;
        getPreferences(MODE_PRIVATE).edit().putInt(KEY_THEME_MODE, newMode).apply();
        final String msg = night ? "Tema chiaro" : "Tema scuro";
        drawerLayout.postDelayed(() -> {
            AppCompatDelegate.setDefaultNightMode(newMode);
            Toast.makeText(MainActivity.this, msg, Toast.LENGTH_SHORT).show();
        }, 200);
    }

    private void showInfoDialog() {
        String version = "1.0";
        try {
            PackageInfo pInfo = getPackageManager().getPackageInfo(getPackageName(), 0);
            version = pInfo.versionName;
        } catch (Exception ignored) {
        }
        String server = ((ChatApplication) getApplication()).getPrefs().getServerUrl();
        new AlertDialog.Builder(this)
            .setTitle("Info")
            .setMessage("ChatAI\nVersione: " + version + "\nServer: " + server)
            .setPositiveButton("OK", null)
            .show();
    }

    private void showGuideDialog() {
        String text = "Benvenuto in ChatAI!\n\n"
            + "• Home: scorri i personaggi e toccali per chattare.\n"
            + "• Categorie: sblocca le categorie con i MevaCoins.\n"
            + "• Daily bonus: ritira la ricompensa giornaliera per guadagnare MVC.\n"
            + "• MevaCoins: usa i MVC per sbloccare categorie e funzionalità extra.\n"
            + "• Menu ☰ in alto a sinistra: Profilo, Cambio tema, Guida, Info.";
        new AlertDialog.Builder(this)
            .setTitle("Guida")
            .setMessage(text)
            .setPositiveButton("OK", null)
            .show();
    }

    private void openPlayStore() {
        String pkg = getPackageName();
        Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse("market://details?id=" + pkg));
        try {
            startActivity(intent);
        } catch (Exception e) {
            startActivity(new Intent(Intent.ACTION_VIEW,
                Uri.parse("https://play.google.com/store/apps/details?id=" + pkg)));
        }
    }

    private void logout() {
        mAuth.clear();
        Intent intent = new Intent(this, LoginActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_NEW_TASK);
        startActivity(intent);
        finish();
    }

    public void openChat(String characterId, String characterName) {
        openChat(characterId, characterName, null, null, null);
    }

    public void openChat(String characterId, String characterName, String initialMessage) {
        openChat(characterId, characterName, initialMessage, null, null);
    }

    public void openChat(String characterId, String characterName, String initialMessage,
                         String avatarImage, String emoji) {
        ChatApplication app = (ChatApplication) getApplication();
        PrefsManager prefs = app.getPrefs();
        prefs.setCharacterId(characterId);

        if (!prefs.hasUsername()) {
            prefs.setUsername("user_" + System.currentTimeMillis());
        }

        // Connect Socket.IO with auth token
        app.connectWithAuth(app.getCurrentUrl());

        MainFragment chatFragment = new MainFragment();
        Bundle args = new Bundle();
        args.putString("character_id", characterId);
        args.putString("character_name", characterName);
        if (initialMessage != null) {
            args.putString("initial_message", initialMessage);
        }
        if (avatarImage != null) {
            args.putString("character_avatar_image", avatarImage);
        }
        if (emoji != null) {
            args.putString("character_emoji", emoji);
        }
        chatFragment.setArguments(args);

        getSupportFragmentManager().beginTransaction()
            .setCustomAnimations(android.R.anim.fade_in, android.R.anim.fade_out)
            .replace(R.id.fragment_container, chatFragment, "main_chat")
            .addToBackStack("main_chat")
            .commit();

        navView.setVisibility(View.GONE);
    }

    public void openGroupChatList() {
        navView.setSelectedItemId(R.id.nav_groups);
    }

    public void openGroupChat(int chatId, String chatName) {
        GroupChatFragment fragment = GroupChatFragment.newInstance(chatId, chatName);
        getSupportFragmentManager().beginTransaction()
            .setCustomAnimations(android.R.anim.fade_in, android.R.anim.fade_out)
            .replace(R.id.fragment_container, fragment, "group_chat")
            .addToBackStack("group_chat")
            .commit();
        navView.setVisibility(View.GONE);
    }

    public void showBottomNav() {
        navView.setVisibility(View.VISIBLE);
    }

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (executor != null) executor.shutdownNow();
        mAdManager.destroyBanner();
    }

    public void showLoading(String message) {
        FrameLayout overlay = findViewById(R.id.loading_overlay);
        TextView loadingText = findViewById(R.id.loading_text);
        LinearProgressIndicator progressBar = findViewById(R.id.loading_progress_bar);
        TextView loadingProgress = findViewById(R.id.loading_progress);
        if (overlay != null) {
            overlay.setVisibility(View.VISIBLE);
            if (loadingText != null) loadingText.setText(message);
            if (progressBar != null) progressBar.setProgress(0);
            if (loadingProgress != null) loadingProgress.setText("");
            VideoView video = findViewById(R.id.loading_video);
            if (video != null) {
                String path = "android.resource://" + getPackageName() + "/" + R.raw.caricamento;
                video.setVideoURI(Uri.parse(path));
                video.setOnPreparedListener(mp -> {
                    mp.setLooping(true);
                    mp.setVolume(0f, 0f);
                    video.start();
                });
            }
        }
    }

    public void updateLoadingProgress(int current, int total, String phase) {
        LinearProgressIndicator progressBar = findViewById(R.id.loading_progress_bar);
        TextView loadingText = findViewById(R.id.loading_text);
        TextView loadingProgress = findViewById(R.id.loading_progress);
        if (progressBar != null && total > 0) {
            int percent = (int) ((current * 100f) / total);
            progressBar.setProgress(percent);
        }
        if (loadingText != null && phase != null) {
            loadingText.setText(phase);
        }
        if (loadingProgress != null) {
            loadingProgress.setText(String.format("%d di %d", current, total));
        }
    }

    public void hideLoading() {
        FrameLayout overlay = findViewById(R.id.loading_overlay);
        if (overlay != null) {
            overlay.setVisibility(View.GONE);
            try {
                VideoView video = findViewById(R.id.loading_video);
                if (video != null) video.stopPlayback();
            } catch (Exception ignored) {}
        }
    }

    // ─── Picture-in-Picture support ──────────────────────────────────
    @Override
    protected void onUserLeaveHint() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.N) {
            // Enter PiP mode when user presses home/gesture navigation
            if (isVideoPlaying()) {
                enterPictureInPictureMode(new PictureInPictureParams.Builder()
                        .setAspectRatio(new Rational(16, 9))
                        .build());
            }
        }
        super.onUserLeaveHint();
    }

    @Override
    public void onPictureInPictureModeChanged(boolean isInPiP, android.content.res.Configuration newConfig) {
        super.onPictureInPictureModeChanged(isInPiP, newConfig);
        // Hide/show UI elements in PiP mode
        if (navView != null) {
            navView.setVisibility(isInPiP ? View.GONE : View.VISIBLE);
        }
        if (topAppBar != null) {
            topAppBar.setVisibility(isInPiP ? View.GONE : View.VISIBLE);
        }
    }

    private boolean isVideoPlaying() {
        // Check if a video is currently playing (e.g., in GroupChatFragment)
        Fragment current = getSupportFragmentManager().findFragmentById(R.id.fragment_container);
        return current != null && (current instanceof GroupChatFragment);
    }
}
