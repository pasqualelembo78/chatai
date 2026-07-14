package com.intelligame.chatai;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.text.TextUtils;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ProgressBar;
import android.widget.Toast;

import org.json.JSONObject;

public class LoginActivity extends Activity {

    private EditText mUsernameView;
    private EditText mPasswordView;
    private EditText mServerUrlView;
    private Button mLoginButton;
    private ProgressBar mProgressBar;

    private AuthManager mAuth;
    private PrefsManager mPrefs;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_login);

        ChatApplication app = (ChatApplication) getApplication();
        mAuth = app.getAuthManager();
        mPrefs = app.getPrefs();

        if (mAuth.isLoggedIn()) {
            checkAdminAndStart();
            return;
        }

        initViews();
    }

    private void initViews() {
        mUsernameView = findViewById(R.id.username_input);
        mPasswordView = findViewById(R.id.password_input);
        mServerUrlView = findViewById(R.id.server_url_input);
        mLoginButton = findViewById(R.id.login_button);
        mProgressBar = findViewById(R.id.auth_progress);

        mLoginButton.setOnClickListener(v -> attemptLogin());

        findViewById(R.id.server_url_toggle).setOnClickListener(v -> {
            mServerUrlView.setVisibility(
                    mServerUrlView.getVisibility() == View.VISIBLE ? View.GONE : View.VISIBLE);
        });

        String savedUrl = mPrefs.getServerUrl();
        mServerUrlView.setText(savedUrl);
        String savedUsername = mAuth.getUsername();
        if (!savedUsername.isEmpty() && !savedUsername.startsWith("user_")) {
            mUsernameView.setText(savedUsername);
        }
    }

    private void attemptLogin() {
        String username = mUsernameView.getText().toString().trim();
        String password = mPasswordView.getText().toString();

        if (TextUtils.isEmpty(username)) {
            mUsernameView.setError("Inserisci un username");
            mUsernameView.requestFocus();
            return;
        }

        if (TextUtils.isEmpty(password)) {
            mPasswordView.setError("Inserisci la password");
            mPasswordView.requestFocus();
            return;
        }

        if (password.length() < 8) {
            mPasswordView.setError("Minimo 8 caratteri");
            mPasswordView.requestFocus();
            return;
        }

        setLoading(true);
        final String serverUrl = getEffectiveServerUrl();

        mAuth.login(username, password, serverUrl, new AuthManager.AuthCallback() {
            @Override
            public void onSuccess(String accessToken, String refreshToken,
                                  String userId, String username, String role, String email) {
                runOnUiThread(() -> {
                    setLoading(false);
                    saveServerUrl(serverUrl);
                    if (!role.equals("admin") && !role.equals("moderator")) {
                        Toast.makeText(LoginActivity.this,
                                "Accesso negato. Solo amministratori possono accedere.", Toast.LENGTH_LONG).show();
                        mAuth.logout();
                        return;
                    }
                    startMainActivity();
                });
            }

            @Override
            public void onError(String error) {
                runOnUiThread(() -> {
                    setLoading(false);
                    Toast.makeText(LoginActivity.this, error, Toast.LENGTH_LONG).show();
                });
            }
        });
    }

    private String getEffectiveServerUrl() {
        String url = mServerUrlView.getText().toString().trim();
        if (url.isEmpty()) {
            url = mPrefs.getServerUrl();
        }
        return url;
    }

    private void saveServerUrl(String url) {
        if (!url.equals(mPrefs.getServerUrl())) {
            mPrefs.setServerUrl(url);
        }
    }

    private void setLoading(boolean loading) {
        mProgressBar.setVisibility(loading ? View.VISIBLE : View.GONE);
        mLoginButton.setEnabled(!loading);
    }

    private void checkAdminAndStart() {
        new Thread(() -> {
            try {
                String url = mPrefs.getServerUrl() + "/user/me";
                AuthManager.HttpResponse resp = mAuth.requestWithRefresh(url, "GET", null, 5000);
                if (resp.statusCode == 200) {
                    JSONObject obj = new JSONObject(resp.body);
                    String role = obj.optString("role", "user");
                    runOnUiThread(() -> {
                        if (role.equals("admin") || role.equals("moderator")) {
                            startMainActivity();
                        } else {
                            mAuth.logout();
                            Toast.makeText(this, "Solo amministratori possono accedere.", Toast.LENGTH_LONG).show();
                        }
                    });
                } else {
                    runOnUiThread(this::startMainActivity);
                }
            } catch (Exception e) {
                runOnUiThread(this::startMainActivity);
            }
        }).start();
    }

    private void startMainActivity() {
        Intent intent = new Intent(this, MainActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_NEW_TASK);
        startActivity(intent);
        finish();
    }
}
