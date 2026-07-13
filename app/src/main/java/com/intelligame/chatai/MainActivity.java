package com.intelligame.chatai;

import android.content.Intent;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.FrameLayout;
import android.widget.TextView;
import android.widget.Toast;

import com.google.android.material.progressindicator.LinearProgressIndicator;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowCompat;
import androidx.fragment.app.Fragment;
import androidx.fragment.app.FragmentTransaction;

import com.google.android.material.bottomnavigation.BottomNavigationView;

public class MainActivity extends AppCompatActivity {

    private BottomNavigationView navView;
    private View fragmentContainer;
    private AuthManager mAuth;
    private AdManager mAdManager;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        ChatApplication app = (ChatApplication) getApplication();
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
        if (!app.getPremiumManager().isPremium()) {
            mAdManager.showAppOpenIfReady(this);
        }

        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);

        setContentView(R.layout.activity_main);

        navView = findViewById(R.id.nav_view);
        fragmentContainer = findViewById(R.id.fragment_container);

        View root = findViewById(R.id.coordinator);
        ViewCompat.setOnApplyWindowInsetsListener(root, (v, insets) -> {
            int sysBottom = insets.getInsets(WindowInsetsCompat.Type.systemBars()).bottom;
            int imeBottom = insets.getInsets(WindowInsetsCompat.Type.ime()).bottom;

            navView.setPadding(0, 0, 0, sysBottom);

            int navHeight = navView.getMeasuredHeight();
            if (navHeight == 0) {
                navHeight = (int) (56 * getResources().getDisplayMetrics().density);
            }
            int contentBottom = imeBottom > 0 ? imeBottom : (sysBottom + navHeight);
            fragmentContainer.setPadding(0, 0, 0, contentBottom);

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
            } else if (itemId == R.id.nav_create) {
                fragment = new CreateFragment();
                tag = "create";
            } else if (itemId == R.id.nav_profile) {
                fragment = new ProfileFragment();
                tag = "profile";
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
            else if (current instanceof CreateFragment) currentId = R.id.nav_create;
            else if (current instanceof ProfileFragment) currentId = R.id.nav_profile;
            navView.setSelectedItemId(currentId);
        }

        handleIntent(getIntent());
        checkDailyBonus();
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
        }
    }

    private void switchFragment(Fragment fragment, String tag) {
        FragmentTransaction transaction = getSupportFragmentManager().beginTransaction()
            .setCustomAnimations(android.R.anim.fade_in, android.R.anim.fade_out)
            .replace(R.id.fragment_container, fragment, tag);
        transaction.commit();
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

    public void showBottomNav() {
        navView.setVisibility(View.VISIBLE);
    }

    @Override
    public void onBackPressed() {
        if (getSupportFragmentManager().getBackStackEntryCount() > 0) {
            getSupportFragmentManager().popBackStackImmediate();
            if (getSupportFragmentManager().getBackStackEntryCount() == 0) {
                navView.setVisibility(View.VISIBLE);
            }
        } else {
            // Show interstitial before closing (if not premium)
            ChatApplication app = (ChatApplication) getApplication();
            if (!app.getPremiumManager().isPremium()) {
                mAdManager.showInterstitialIfReady(this);
            }
            super.onBackPressed();
        }
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
        }
    }

    private void checkDailyBonus() {
        AuthManager auth = ((ChatApplication) getApplication()).getAuthManager();
        if (auth != null && auth.getAccessToken() != null && !auth.getAccessToken().isEmpty()) {
            new Handler(Looper.getMainLooper()).postDelayed(() -> {
                DailyBonusDialog dialog = new DailyBonusDialog();
                dialog.show(getSupportFragmentManager(), "daily_bonus");
            }, 1500);
        }
    }

    public void showBonusSnackbar(int earned) {
        View contentView = findViewById(android.R.id.content);
        if (contentView != null) {
            com.google.android.material.snackbar.Snackbar.make(contentView, 
                "+" + earned + " MVC riscossi!", 
                com.google.android.material.snackbar.Snackbar.LENGTH_LONG).show();
        }
    }
}
