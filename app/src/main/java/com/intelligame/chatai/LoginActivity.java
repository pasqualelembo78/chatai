package com.intelligame.chatai;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.text.TextUtils;
import android.text.method.HideReturnsTransformationMethod;
import android.text.method.PasswordTransformationMethod;
import android.view.View;
import android.widget.Button;
import android.widget.EditText;
import android.widget.ProgressBar;
import android.widget.TextView;
import android.widget.Toast;

import com.google.android.gms.auth.api.signin.GoogleSignIn;
import com.google.android.gms.auth.api.signin.GoogleSignInAccount;
import com.google.android.gms.auth.api.signin.GoogleSignInClient;
import com.google.android.gms.auth.api.signin.GoogleSignInOptions;
import com.google.android.gms.common.SignInButton;
import com.google.android.gms.common.api.ApiException;
import com.google.android.gms.tasks.Task;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;

public class LoginActivity extends Activity {

    private static final int RC_GOOGLE_SIGN_IN = 100;

    private SignInButton mGoogleSignInButton;
    private EditText mUsernameView;
    private EditText mEmailView;
    private EditText mPasswordView;
    private EditText mServerUrlView;
    private EditText mReferralCodeView;
    private Button mLoginButton;
    private TextView mToggleAuthMode;
    private ProgressBar mProgressBar;

    private AuthManager mAuth;
    private PrefsManager mPrefs;
    private GoogleSignInClient mGoogleSignInClient;
    private String mGoogleClientId;
    private boolean mIsSignupMode = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        setContentView(R.layout.activity_login);

        ChatApplication app = (ChatApplication) getApplication();
        mAuth = app.getAuthManager();
        mPrefs = app.getPrefs();

        if (!mPrefs.isPrivacyAccepted()) {
            showPrivacyConsent();
            return;
        }

        initViews();

        if (mAuth.isLoggedIn()) {
            startMainActivity();
        }
    }

    private void initViews() {
        mGoogleSignInButton = findViewById(R.id.google_sign_in_button);
        mGoogleSignInButton.setVisibility(View.GONE);

        mUsernameView = findViewById(R.id.username_input);
        mEmailView = findViewById(R.id.email_input);
        mPasswordView = findViewById(R.id.password_input);
        mServerUrlView = findViewById(R.id.server_url_input);
        mReferralCodeView = findViewById(R.id.referral_code_input);
        mLoginButton = findViewById(R.id.login_button);
        mProgressBar = findViewById(R.id.auth_progress);
        mToggleAuthMode = findViewById(R.id.toggle_auth_mode);

        mLoginButton.setOnClickListener(v -> {
            if (mIsSignupMode) {
                attemptRegister();
            } else {
                attemptLogin();
            }
        });

        mToggleAuthMode.setOnClickListener(v -> toggleAuthMode());

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

        fetchGoogleClientId();
    }

    private void toggleAuthMode() {
        mIsSignupMode = !mIsSignupMode;
        if (mIsSignupMode) {
            mLoginButton.setText("REGISTRATI");
            mToggleAuthMode.setText("Hai già account? Accedi");
            mEmailView.setVisibility(View.VISIBLE);
        } else {
            mLoginButton.setText("ACCEDI");
            mToggleAuthMode.setText("Non hai account? Registrati");
            mEmailView.setVisibility(View.GONE);
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
            setLoading(false);
            return;
        }

        if (password.length() < 8) {
            mPasswordView.setError("Minimo 8 caratteri");
            mPasswordView.requestFocus();
            setLoading(false);
            return;
        }

        setLoading(true);
        final String serverUrl = getEffectiveServerUrl();
        final String referralCode = mReferralCodeView.getText().toString().trim();

        mAuth.login(username, password, serverUrl, new AuthManager.AuthCallback() {
            @Override
            public void onSuccess(String accessToken, String refreshToken,
                                  String userId, String username, String role, String email) {
                runOnUiThread(() -> {
                    setLoading(false);
                    saveServerUrl(serverUrl);
                    checkAndRedirect(serverUrl);
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

    private void attemptRegister() {
        String username = mUsernameView.getText().toString().trim();
        String email = mEmailView.getText().toString().trim();
        String password = mPasswordView.getText().toString();
        String referralCode = mReferralCodeView.getText().toString().trim();

        if (TextUtils.isEmpty(username)) {
            mUsernameView.setError("Inserisci un username");
            mUsernameView.requestFocus();
            return;
        }
        if (username.length() < 3) {
            mUsernameView.setError("Minimo 3 caratteri");
            mUsernameView.requestFocus();
            return;
        }
        if (TextUtils.isEmpty(password)) {
            mPasswordView.setError("Inserisci una password");
            mPasswordView.requestFocus();
            return;
        }
        if (password.length() < 8) {
            mPasswordView.setError("Minimo 8 caratteri");
            mPasswordView.requestFocus();
            return;
        }
        if (!email.isEmpty() && !android.util.Patterns.EMAIL_ADDRESS.matcher(email).matches()) {
            mEmailView.setError("Email non valida");
            mEmailView.requestFocus();
            return;
        }

        setLoading(true);
        final String serverUrl = getEffectiveServerUrl();
        mAuth.register(username, email, password, serverUrl,
                referralCode.isEmpty() ? null : referralCode,
                new AuthManager.AuthCallback() {
                    @Override
                    public void onSuccess(String accessToken, String refreshToken,
                                          String userId, String username, String role, String email) {
                        runOnUiThread(() -> {
                            setLoading(false);
                            saveServerUrl(serverUrl);
                            Toast.makeText(LoginActivity.this,
                                    "Benvenuto, " + username + "!", Toast.LENGTH_SHORT).show();
                            checkAndRedirect(serverUrl);
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

    private void fetchGoogleClientId() {
        new Thread(() -> {
            try {
                String serverUrl = getEffectiveServerUrl();
                URL url = new URL(serverUrl + "/auth/google/client-id");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setConnectTimeout(5000);
                int code = conn.getResponseCode();
                if (code == 200) {
                    BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                    StringBuilder resp = new StringBuilder();
                    String line;
                    while ((line = reader.readLine()) != null) resp.append(line);
                    reader.close();
                    conn.disconnect();
                    JSONObject obj = new JSONObject(resp.toString());
                    mGoogleClientId = obj.optString("client_id", "");
                    runOnUiThread(() -> {
                        if (!mGoogleClientId.isEmpty()) {
                            mGoogleSignInButton.setVisibility(View.VISIBLE);
                            mGoogleSignInButton.setOnClickListener(v -> signInWithGoogle());
                        }
                    });
                }
            } catch (Exception ignored) {}
        }).start();
    }

    private void signInWithGoogle() {
        if (mGoogleClientId == null || mGoogleClientId.isEmpty()) {
            Toast.makeText(this,
                    "Google Sign-In non disponibile. Usa l'accesso senza password.",
                    Toast.LENGTH_LONG).show();
            return;
        }

        GoogleSignInOptions gso = new GoogleSignInOptions.Builder(GoogleSignInOptions.DEFAULT_SIGN_IN)
                .requestIdToken(mGoogleClientId)
                .requestEmail()
                .build();
        mGoogleSignInClient = GoogleSignIn.getClient(this, gso);

        Intent signInIntent = mGoogleSignInClient.getSignInIntent();
        startActivityForResult(signInIntent, RC_GOOGLE_SIGN_IN);
    }

    @Override
    protected void onActivityResult(int requestCode, int resultCode, Intent data) {
        super.onActivityResult(requestCode, resultCode, data);

        if (requestCode == RC_GOOGLE_SIGN_IN) {
            Task<GoogleSignInAccount> task = GoogleSignIn.getSignedInAccountFromIntent(data);
            try {
                GoogleSignInAccount account = task.getResult(ApiException.class);
                String idToken = account.getIdToken();
                if (idToken != null) {
                    final String serverUrl = getEffectiveServerUrl();
                    final String referralCode = mReferralCodeView.getText().toString().trim();
                    setLoading(true);
                    mAuth.loginWithGoogle(idToken, serverUrl, referralCode.isEmpty() ? null : referralCode, new AuthManager.AuthCallback() {
                        @Override
                        public void onSuccess(String accessToken, String refreshToken,
                                              String userId, String username, String role, String email) {
                            runOnUiThread(() -> {
                                setLoading(false);
                                saveServerUrl(serverUrl);
                                Toast.makeText(LoginActivity.this,
                                        "Benvenuto, " + username + "!", Toast.LENGTH_SHORT).show();
                                checkAndRedirect(serverUrl);
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
                } else {
                    Toast.makeText(this, "Errore: id_token nullo", Toast.LENGTH_SHORT).show();
                }
            } catch (ApiException e) {
                setLoading(false);
                Toast.makeText(this, "Google Sign-In fallito: " + e.getMessage(), Toast.LENGTH_SHORT).show();
            }
        }
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

    private void showPrivacyConsent() {
        new android.app.AlertDialog.Builder(this)
                .setTitle("Privacy Policy")
                .setMessage(
                        "Aria raccoglie i seguenti dati:\n\n"
                        + "• Username — scelto all'accesso\n"
                        + "• Email — solo se utilizzi Google Sign-In\n"
                        + "• Messaggi di chat — testo delle conversazioni\n"
                        + "• Audio — solo per trascrizione vocale, cancellato dopo 5 minuti\n"
                        + "• Immagini — solo per descrizione AI, cancellate dopo 5 minuti\n\n"
                        + "I dati NON vengono venduti a terzi. "
                        + "Le richieste AI sono inviate a provider esterni "
                        + "senza dati identificativi (username, email, IP non vengono trasmessi).\n\n"
                        + "Conservazione dei dati:\n"
                        + "• Messaggi chat: fino a 90 giorni\n"
                        + "• Account: fino a richiesta di cancellazione\n\n"
                        + "I personaggi e i messaggi sono GENERATI DALL'INTELLIGENZA ARTIFICIALE "
                        + "e non rappresentano persone reali.\n\n"
                        + "Puoi esercitare i tuoi diritti GDPR (accesso, rettifica, cancellazione) "
                        + "dalle impostazioni dell'app o contattandoci a lembopasquale78@gmail.com.\n\n"
                        + "Utilizzando l'app dichiari di essere maggiorenne (18+).\n\n"
                        + "Consenti la raccolta di questi dati per utilizzare l'app?"
                )
                .setCancelable(false)
                .setPositiveButton("ACCETTO", (d, w) -> {
                    mPrefs.setPrivacyAccepted(true);
                    initViews();
                    if (mAuth.isLoggedIn()) {
                        startMainActivity();
                    }
                })
                .setNegativeButton("RIFIUTO", (d, w) -> finish())
                .show();
    }

    private void startMainActivity() {
        Intent intent = new Intent(this, MainActivity.class);
        intent.addFlags(Intent.FLAG_ACTIVITY_CLEAR_TOP | Intent.FLAG_ACTIVITY_NEW_TASK);
        startActivity(intent);
        finish();
    }

    private void checkAndRedirect(String serverUrl) {
        new Thread(() -> {
            try {
                String token = mAuth.getAccessToken();
                URL url = new URL(serverUrl.replace("/chat", "") + "/user/preferences");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestProperty("Authorization", "Bearer " + token);
                conn.setConnectTimeout(5000);
                String json = readStream(conn.getInputStream());
                conn.disconnect();
                JSONObject obj = new JSONObject(json);
                String gender = obj.optString("gender_interest", "");
                runOnUiThread(() -> {
                    if (gender.isEmpty()) {
                        Intent i = new Intent(LoginActivity.this, OnboardingActivity.class);
                        startActivity(i);
                    } else {
                        startMainActivity();
                    }
                });
            } catch (Exception e) {
                runOnUiThread(() -> startMainActivity());
            }
        }).start();
    }

    private String readStream(java.io.InputStream is) throws Exception {
        java.util.Scanner s = new java.util.Scanner(is).useDelimiter("\\A");
        return s.hasNext() ? s.next() : "";
    }
}
