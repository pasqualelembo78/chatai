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

import com.google.android.material.button.MaterialButton;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.Calendar;
import java.util.Locale;

public class LoginActivity extends Activity {

    private EditText mUsernameView;
    private EditText mEmailView;
    private EditText mPasswordView;
    private EditText mServerUrlView;
    private EditText mReferralCodeView;
    private View mBirthDateRow;
    private EditText mBirthDay;
    private EditText mBirthMonth;
    private EditText mBirthYear;
    private Button mLoginButton;
    private TextView mToggleAuthMode;
    private ProgressBar mProgressBar;

    private AuthManager mAuth;
    private PrefsManager mPrefs;
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
        mUsernameView = findViewById(R.id.username_input);
        mEmailView = findViewById(R.id.email_input);
        mPasswordView = findViewById(R.id.password_input);
        mServerUrlView = findViewById(R.id.server_url_input);
        mReferralCodeView = findViewById(R.id.referral_code_input);
        mBirthDateRow = findViewById(R.id.birth_date_row);
        mBirthDay = findViewById(R.id.birth_day);
        mBirthMonth = findViewById(R.id.birth_month);
        mBirthYear = findViewById(R.id.birth_year);
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
    }

    private void toggleAuthMode() {
        mIsSignupMode = !mIsSignupMode;
        if (mIsSignupMode) {
            mLoginButton.setText("REGISTRATI");
            mToggleAuthMode.setText("Hai già account? Accedi");
            mEmailView.setVisibility(View.VISIBLE);
            mBirthDateRow.setVisibility(View.VISIBLE);
        } else {
            mLoginButton.setText("ACCEDI");
            mToggleAuthMode.setText("Non hai account? Registrati");
            mEmailView.setVisibility(View.GONE);
            mBirthDateRow.setVisibility(View.GONE);
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

        // Neutral age screen: l'utente inserisce liberamente giorno/mese/anno di nascita.
        int day, month, year;
        try {
            day = Integer.parseInt(mBirthDay.getText().toString().trim());
            month = Integer.parseInt(mBirthMonth.getText().toString().trim());
            year = Integer.parseInt(mBirthYear.getText().toString().trim());
        } catch (NumberFormatException e) {
            day = month = year = -1;
        }
        if (day < 1 || month < 1 || year < 1900) {
            Toast.makeText(LoginActivity.this,
                    "Inserisci la data di nascita (GG/MM/AAAA).", Toast.LENGTH_LONG).show();
            setLoading(false);
            return;
        }
        Calendar dob = Calendar.getInstance();
        dob.set(year, month - 1, day);
        if (dob.get(Calendar.YEAR) != year || dob.get(Calendar.MONTH) != month - 1) {
            Toast.makeText(LoginActivity.this, "Data di nascita non valida.", Toast.LENGTH_LONG).show();
            setLoading(false);
            return;
        }
        int age = Calendar.getInstance().get(Calendar.YEAR) - year;
        if (Calendar.getInstance().get(Calendar.DAY_OF_YEAR) < dob.get(Calendar.DAY_OF_YEAR)) age--;
        if (age < 18) {
            Toast.makeText(LoginActivity.this,
                    "Devi avere almeno 18 anni per registrarti.", Toast.LENGTH_LONG).show();
            setLoading(false);
            return;
        }
        final String birthDate = String.format(Locale.ITALY, "%04d-%02d-%02d", year, month, day);
        final int birthYear = year;

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
                            mPrefs.setAdultBirthYear(birthYear);
                            verifyAgeOnServer(serverUrl, birthYear);
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

    private String getEffectiveServerUrl() {
        String url = mServerUrlView.getText().toString().trim();
        if (url.isEmpty()) {
            url = mPrefs.getServerUrl();
        }
        return url;
    }

    private void verifyAgeOnServer(final String serverUrl, final int birthYear) {
        new Thread(() -> {
            try {
                JSONObject body = new JSONObject();
                body.put("birth_year", birthYear);
                mAuth.requestWithRefresh(serverUrl + "/me/verify-age", "POST", body.toString(), 8000);
            } catch (Exception ignored) {
            }
        }).start();
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
                        + "• Email — utilizzata per la registrazione e il recupero account\n"
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
