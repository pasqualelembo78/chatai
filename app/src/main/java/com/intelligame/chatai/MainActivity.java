package com.intelligame.chatai;

import android.content.Intent;
import android.os.Bundle;
import android.view.View;
import android.widget.FrameLayout;
import android.widget.TextView;

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

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        ChatApplication app = (ChatApplication) getApplication();
        mAuth = app.getAuthManager();

        if (!mAuth.isLoggedIn()) {
            Intent intent = new Intent(this, LoginActivity.class);
            intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_NEW_TASK);
            startActivity(intent);
            finish();
            return;
        }

        WindowCompat.setDecorFitsSystemWindows(getWindow(), false);
        setContentView(R.layout.activity_main);

        navView = findViewById(R.id.nav_view);
        fragmentContainer = findViewById(R.id.fragment_container);

        View root = findViewById(R.id.coordinator);
        ViewCompat.setOnApplyWindowInsetsListener(root, (v, insets) -> {
            int sysBottom = insets.getInsets(WindowInsetsCompat.Type.systemBars()).bottom;
            navView.setPadding(0, 0, 0, sysBottom);
            int navHeight = navView.getMeasuredHeight();
            if (navHeight == 0) {
                navHeight = (int) (56 * getResources().getDisplayMetrics().density);
            }
            fragmentContainer.setPadding(0, 0, 0, sysBottom + navHeight);
            return WindowInsetsCompat.CONSUMED;
        });

        navView.setOnItemSelectedListener(item -> {
            int itemId = item.getItemId();
            Fragment fragment = null;
            String tag = null;

            if (itemId == R.id.nav_dashboard) {
                fragment = new DashboardFragment();
                tag = "dashboard";
            } else if (itemId == R.id.nav_users) {
                fragment = new UsersFragment();
                tag = "users";
            } else if (itemId == R.id.nav_logs) {
                fragment = new AuditLogFragment();
                tag = "logs";
            } else if (itemId == R.id.nav_moderation) {
                fragment = new ModerationFragment();
                tag = "moderation";
            } else if (itemId == R.id.nav_import) {
                fragment = new ImportFragment();
                tag = "import";
            }

            if (fragment != null) {
                switchFragment(fragment, tag);
            }
            return true;
        });

        if (savedInstanceState == null) {
            getSupportFragmentManager().beginTransaction()
                .add(R.id.fragment_container, new DashboardFragment(), "dashboard")
                .commit();
        } else {
            Fragment current = getSupportFragmentManager().findFragmentById(R.id.fragment_container);
            int currentId = R.id.nav_dashboard;
            if (current instanceof UsersFragment) currentId = R.id.nav_users;
            else if (current instanceof AuditLogFragment) currentId = R.id.nav_logs;
            else if (current instanceof ModerationFragment) currentId = R.id.nav_moderation;
            else if (current instanceof ImportFragment) currentId = R.id.nav_import;
            navView.setSelectedItemId(currentId);
        }
    }

    private void switchFragment(Fragment fragment, String tag) {
        getSupportFragmentManager().beginTransaction()
            .setCustomAnimations(android.R.anim.fade_in, android.R.anim.fade_out)
            .replace(R.id.fragment_container, fragment, tag)
            .commit();
    }

    public void loadFragment(Fragment fragment, String tag) {
        getSupportFragmentManager().beginTransaction()
            .setCustomAnimations(android.R.anim.fade_in, android.R.anim.fade_out)
            .replace(R.id.fragment_container, fragment, tag)
            .addToBackStack(tag)
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
            super.onBackPressed();
        }
    }
}
