package com.intelligame.chatai;

import android.app.Activity;
import android.content.Intent;
import android.os.Bundle;
import android.text.InputType;
import android.text.TextUtils;
import android.text.method.HideReturnsTransformationMethod;
import android.text.method.PasswordTransformationMethod;
import android.view.View;
import android.widget.Button;
import android.widget.CheckBox;
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
    private EditText mBirthDateView;
    private CheckBox mAgeConfirmCheckbox;
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
        mBirthDateView = findViewById(R.id.birth_date_input);
        mAgeConfirmCheckbox = findViewById(R.id.age_confirm_checkbox);
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
            mBirthDateView.setVisibility(View.VISIBLE);
            mAgeConfirmCheckbox.setVisibility(View.VISIBLE);
        } else {
            mLoginButton.setText("ACCEDI");
            mToggleAuthMode.setText("Non hai account? Registrati");
            mEmailView.setVisibility(View.GONE);
            mBirthDateView.setVisibility(View.GONE);
            mAgeConfirmCheckbox.setVisibility(View.GONE);
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

        // Age verification: must confirm 18+ and provide a valid birth date.
        if (!mAgeConfirmCheckbox.isChecked()) {
            Toast.makeText(LoginActivity.this,
                    "Devi confermare di avere almeno 18 anni.", Toast.LENGTH_LONG).show();
            setLoading(false);
            return;
        }
        final String birthDate = parseAndValidateBirthDate();
        if (birthDate == null) {
            setLoading(false);
            return;
        }

        setLoading(true);
        final String serverUrl = getEffectiveServerUrl();
        mAuth.register(username, email, password, serverUrl,
                referralCode.isEmpty() ? null : referralCode, birthDate,
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
                    mAuth.loginWithGoogle(idToken, serverUrl,
                            referralCode.isEmpty() ? null : referralCode, null,
                            googleAuthCallback(idToken, serverUrl,
                                    referralCode.isEmpty() ? null : referralCode, true));
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

    private String parseAndValidateBirthDate() {
        String raw = mBirthDateView.getText().toString().trim();
        if (raw.isEmpty()) {
            mBirthDateView.setError("Inserisci la data di nascita");
            mBirthDateView.requestFocus();
            return null;
        }
        java.text.DateFormat[] fmts = {
                new java.text.SimpleDateFormat("dd/MM/yyyy", java.util.Locale.ITALY),
                new java.text.SimpleDateFormat("yyyy-MM-dd", java.util.Locale.ITALY)
        };
        java.util.Date birth = null;
        for (java.text.DateFormat f : fmts) {
            try { birth = f.parse(raw); break; } catch (Exception ignored) {}
        }
        if (birth == null) {
            mBirthDateView.setError("Formato non valido (GG/MM/AAAA)");
            mBirthDateView.requestFocus();
            return null;
        }
        java.util.Calendar b = java.util.Calendar.getInstance();
        b.setTime(birth);
        java.util.Calendar now = java.util.Calendar.getInstance();
        int age = now.get(java.util.Calendar.YEAR) - b.get(java.util.Calendar.YEAR);
        if (now.get(java.util.Calendar.DAY_OF_YEAR) < b.get(java.util.Calendar.DAY_OF_YEAR)) {
            age--;
        }
        if (age < 18) {
            Toast.makeText(LoginActivity.this,
                    "L'iscrizione è riservata agli utenti di almeno 18 anni.",
                    Toast.LENGTH_LONG).show();
            return null;
        }
        return new java.text.SimpleDateFormat("yyyy-MM-dd", java.util.Locale.ITALY).format(birth);
    }

    private String validateBirthDateString(String raw) {
        if (raw.isEmpty()) {
            Toast.makeText(this, "Inserisci la data di nascita", Toast.LENGTH_LONG).show();
            return null;
        }
        java.text.DateFormat[] fmts = {
                new java.text.SimpleDateFormat("dd/MM/yyyy", java.util.Locale.ITALY),
                new java.text.SimpleDateFormat("yyyy-MM-dd", java.util.Locale.ITALY)
        };
        java.util.Date birth = null;
        for (java.text.DateFormat f : fmts) {
            try { birth = f.parse(raw); break; } catch (Exception ignored) {}
        }
        if (birth == null) {
            Toast.makeText(this, "Formato non valido (GG/MM/AAAA)", Toast.LENGTH_LONG).show();
            return null;
        }
        java.util.Calendar b = java.util.Calendar.getInstance();
        b.setTime(birth);
        java.util.Calendar now = java.util.Calendar.getInstance();
        int age = now.get(java.util.Calendar.YEAR) - b.get(java.util.Calendar.YEAR);
        if (now.get(java.util.Calendar.DAY_OF_YEAR) < b.get(java.util.Calendar.DAY_OF_YEAR)) {
            age--;
        }
        if (age < 18) {
            Toast.makeText(this, "L'iscrizione è riservata agli utenti di almeno 18 anni.", Toast.LENGTH_LONG).show();
            return null;
        }
        return new java.text.SimpleDateFormat("yyyy-MM-dd", java.util.Locale.ITALY).format(birth);
    }

    private AuthManager.AuthCallback googleAuthCallback(final String idToken, final String serverUrl,
                                                        final String referralCode, final boolean allowAgePrompt) {
        return new AuthManager.AuthCallback() {
            @Override
            public void onSuccess(String accessToken, String refreshToken, String userId, String username, String role, String email) {
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
                    String e = error == null ? "" : error.toLowerCase();
                    if (allowAgePrompt && (e.contains("18") || e.contains("età")
                            || e.contains("minoren") || e.contains("riservata"))) {
                        showGoogleAgeDialog(idToken, serverUrl, referralCode);
                    } else {
                        setLoading(false);
                        Toast.makeText(LoginActivity.this, error, Toast.LENGTH_LONG).show();
                    }
                });
            }
        };
    }

    private void showGoogleAgeDialog(final String idToken, final String serverUrl, final String referralCode) {
        android.app.AlertDialog.Builder builder = new android.app.AlertDialog.Builder(this);
        builder.setTitle("Verifica età (obbligatoria)");
        android.widget.LinearLayout layout = new android.widget.LinearLayout(this);
        layout.setOrientation(android.widget.LinearLayout.VERTICAL);
        layout.setPadding(50, 40, 50, 10);
        final android.widget.EditText dob = new android.widget.EditText(this);
        dob.setHint("Data di nascita (GG/MM/AAAA)");
        dob.setInputType(InputType.TYPE_CLASS_DATETIME | InputType.TYPE_DATETIME_VARIATION_DATE);
        final android.widget.CheckBox cb = new android.widget.CheckBox(this);
        cb.setText("Confermo di avere almeno 18 anni");
        layout.addView(dob);
        layout.addView(cb);
        builder.setView(layout);
        builder.setCancelable(false);
        builder.setPositiveButton("CONFERMA", (d, w) -> {
            if (!cb.isChecked()) {
                Toast.makeText(LoginActivity.this,
                        "Devi confermare di avere almeno 18 anni.", Toast.LENGTH_LONG).show();
                return;
            }
            String bd = validateBirthDateString(dob.getText().toString().trim());
            if (bd == null) return;
            mAuth.loginWithGoogle(idToken, serverUrl, referralCode, bd,
                    googleAuthCallback(idToken, serverUrl, referralCode, false));
        });
        builder.setNegativeButton("ANNULLA", (d, w) -> setLoading(false));
        builder.show();
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
                String apiUrl = serverUrl.replace("/chat", "") + "/user/preferences";
                AuthManager.HttpResponse httpResp = mAuth.requestWithRefresh(apiUrl, "GET", null, 5000);
                if (httpResp.statusCode == 200) {
                    JSONObject obj = new JSONObject(httpResp.body);
                    String gender = obj.optString("gender_interest", "");
                    runOnUiThread(() -> {
                        if (gender.isEmpty()) {
                            Intent i = new Intent(LoginActivity.this, OnboardingActivity.class);
                            startActivity(i);
                        } else {
                            startMainActivity();
                        }
                    });
                } else {
                    runOnUiThread(this::startMainActivity);
                }
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
