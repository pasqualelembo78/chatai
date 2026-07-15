package com.intelligame.chatai;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.view.View;
import android.widget.FrameLayout;
import android.widget.TextView;
import android.widget.Toast;
import android.widget.VideoView;

import com.google.android.material.badge.BadgeDrawable;
import com.google.android.material.progressindicator.LinearProgressIndicator;

import androidx.appcompat.app.AppCompatActivity;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;
import androidx.core.view.WindowCompat;
import androidx.fragment.app.Fragment;
import androidx.fragment.app.FragmentTransaction;

import com.google.android.material.bottomnavigation.BottomNavigationView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

public class MainActivity extends AppCompatActivity {

    private BottomNavigationView navView;
    private View fragmentContainer;
    private AuthManager mAuth;
    private AdManager mAdManager;
    private ExecutorService executor = Executors.newSingleThreadExecutor();
    private Handler mainHandler = new Handler(Looper.getMainLooper());
    private int pendingInvitations = 0;

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
    }

    @Override
    protected void onResume() {
        super.onResume();
        checkPendingInvitations();
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

    @Override
    protected void onDestroy() {
        super.onDestroy();
        if (executor != null) executor.shutdownNow();
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

}
