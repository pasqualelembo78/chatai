package com.intelligame.chatai;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Log;

import androidx.security.crypto.EncryptedSharedPreferences;
import androidx.security.crypto.MasterKey;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;

public class AuthManager {

    private static final String TAG = "AuthManager";
    private static final String PREFS_NAME = "auth_prefs_encrypted";
    private static final String KEY_ACCESS_TOKEN = "access_token";
    private static final String KEY_REFRESH_TOKEN = "refresh_token";
    private static final String KEY_USER_ID = "user_id";
    private static final String KEY_USERNAME = "username";
    private static final String KEY_ROLE = "role";
    private static final String KEY_EMAIL = "email";
    private static final String KEY_PERSISTENT_TOKEN = "persistent_token";

    private SharedPreferences prefs;
    private final String baseUrl;

    public AuthManager(Context context, String baseUrl) {
        this.baseUrl = baseUrl;
        try {
            MasterKey masterKey = new MasterKey.Builder(context)
                    .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                    .build();
            this.prefs = EncryptedSharedPreferences.create(
                    context,
                    PREFS_NAME,
                    masterKey,
                    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            );
        } catch (Exception e) {
            Log.e(TAG, "EncryptedSharedPreferences unavailable - security feature required", e);
            throw new SecurityException("EncryptedSharedPreferences is required for secure token storage", e);
        }
    }

    public boolean isLoggedIn() {
        return !prefs.getString(KEY_ACCESS_TOKEN, "").isEmpty();
    }

    public String getAccessToken() {
        return prefs.getString(KEY_ACCESS_TOKEN, "");
    }

    public String getRefreshToken() {
        return prefs.getString(KEY_REFRESH_TOKEN, "");
    }

    public String getUserId() {
        return prefs.getString(KEY_USER_ID, "");
    }

    public String getUsername() {
        return prefs.getString(KEY_USERNAME, "");
    }

    public String getRole() {
        return prefs.getString(KEY_ROLE, "user");
    }

    public String getEmail() {
        return prefs.getString(KEY_EMAIL, "");
    }

    public String getPersistentToken() {
        return prefs.getString(KEY_PERSISTENT_TOKEN, "");
    }

    public void saveTokens(String accessToken, String refreshToken, String userId, String username, String role, String email) {
        prefs.edit()
                .putString(KEY_ACCESS_TOKEN, accessToken)
                .putString(KEY_REFRESH_TOKEN, refreshToken)
                .putString(KEY_USER_ID, userId)
                .putString(KEY_USERNAME, username)
                .putString(KEY_ROLE, role != null ? role : "user")
                .putString(KEY_EMAIL, email != null ? email : "")
                .apply();
    }

    public void savePersistentToken(String persistentToken) {
        prefs.edit().putString(KEY_PERSISTENT_TOKEN, persistentToken != null ? persistentToken : "").apply();
    }

    public void loginLocal(String username, String serverUrl, AuthCallback callback) {
        loginLocal(username, serverUrl, null, callback);
    }

    public void loginLocal(String username, String serverUrl, String referralCode, AuthCallback callback) {
        final String urlStr = serverUrl + "/auth/local-login";
        new Thread(() -> {
            HttpURLConnection conn = null;
            try {
                URL url = new URL(urlStr);
                conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setConnectTimeout(20000);
                conn.setReadTimeout(20000);
                conn.setRequestProperty("Content-Type", "application/json");
                conn.setDoOutput(true);

                JSONObject body = new JSONObject();
                body.put("username", username);
                if (referralCode != null && !referralCode.isEmpty()) {
                    body.put("referral_code", referralCode);
                }

                OutputStream os = conn.getOutputStream();
                os.write(body.toString().getBytes());
                os.close();

                int code = conn.getResponseCode();
                if (code == 200 || code == 201) {
                    BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                    StringBuilder response = new StringBuilder();
                    String line;
                    while ((line = reader.readLine()) != null) response.append(line);
                    reader.close();

                    JSONObject json = new JSONObject(response.toString());
                    String accessToken = json.getString("access_token");
                    String refreshToken = json.getString("refresh_token");
                    String persistentToken = json.optString("persistent_token", "");
                    JSONObject user = json.getJSONObject("user");
                    String userId = user.getString("id");
                    String role = user.optString("role", "user");

                    saveTokens(accessToken, refreshToken, userId, username, role, "");
                    if (!persistentToken.isEmpty()) savePersistentToken(persistentToken);
                    callback.onSuccess(accessToken, refreshToken, userId, username, role, "");
                } else {
                    String errMsg = "Errore login locale (" + code + ")";
                    try {
                        BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getErrorStream()));
                        StringBuilder response = new StringBuilder();
                        String line;
                        while ((line = reader.readLine()) != null) response.append(line);
                        reader.close();
                        errMsg = new JSONObject(response.toString()).optString("error", errMsg);
                    } catch (Exception ignored) {}
                    callback.onError(errMsg);
                }
            } catch (Exception e) {
                Log.e(TAG, "Local login error", e);
                callback.onError("Connessione al server fallita: " + e.getMessage());
            } finally {
                if (conn != null) conn.disconnect();
            }
        }).start();
    }

    public void createLocalSession(String username) {
        String userId = "local_" + System.currentTimeMillis();
        prefs.edit()
                .putString(KEY_ACCESS_TOKEN, "local_session")
                .putString(KEY_REFRESH_TOKEN, "local_session")
                .putString(KEY_USER_ID, userId)
                .putString(KEY_USERNAME, username)
                .putString(KEY_ROLE, "user")
                .putString(KEY_EMAIL, "")
                .apply();
    }

    public void clear() {
        prefs.edit()
                .remove(KEY_ACCESS_TOKEN)
                .remove(KEY_REFRESH_TOKEN)
                .remove(KEY_USER_ID)
                .remove(KEY_USERNAME)
                .remove(KEY_ROLE)
                .remove(KEY_EMAIL)
                .remove(KEY_PERSISTENT_TOKEN)
                .apply();
    }

    public String getAuthorizationHeader() {
        String token = getAccessToken();
        if (token.isEmpty()) return "";
        return "Bearer " + token;
    }

    public interface AuthCallback {
        void onSuccess(String accessToken, String refreshToken, String userId, String username, String role, String email);
        void onError(String error);
    }

    public void login(String username, String password, String serverUrl, AuthCallback callback) {
        login(username, password, serverUrl, null, callback);
    }

    public void login(String username, String password, String serverUrl, String referralCode, AuthCallback callback) {
        final String urlStr = serverUrl + "/auth/login";
        new Thread(() -> {
            HttpURLConnection conn = null;
            try {
                URL url = new URL(urlStr);
                conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setConnectTimeout(15000);
                conn.setReadTimeout(15000);
                conn.setRequestProperty("Content-Type", "application/json");
                conn.setDoOutput(true);

                JSONObject body = new JSONObject();
                body.put("username", username);
                body.put("password", password);
                if (referralCode != null && !referralCode.isEmpty()) {
                    body.put("referral_code", referralCode);
                }

                OutputStream os = conn.getOutputStream();
                os.write(body.toString().getBytes());
                os.close();

                int code = conn.getResponseCode();
                if (code == 200) {
                    BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                    StringBuilder response = new StringBuilder();
                    String line;
                    while ((line = reader.readLine()) != null) response.append(line);
                    reader.close();

                    JSONObject json = new JSONObject(response.toString());
                    String accessToken = json.getString("access_token");
                    String refreshToken = json.getString("refresh_token");
                    String persistentToken = json.optString("persistent_token", "");
                    JSONObject user = json.getJSONObject("user");
                    String userId = user.getString("id");
                    String role = user.optString("role", "user");

                    saveTokens(accessToken, refreshToken, userId, username, role, "");
                    if (!persistentToken.isEmpty()) savePersistentToken(persistentToken);
                    callback.onSuccess(accessToken, refreshToken, userId, username, role, "");
                } else {
                    BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getErrorStream()));
                    StringBuilder response = new StringBuilder();
                    String line;
                    while ((line = reader.readLine()) != null) response.append(line);
                    reader.close();
                    String msg = new JSONObject(response.toString()).optString("error", "Errore login");
                    callback.onError(msg);
                }
            } catch (Exception e) {
                Log.e(TAG, "Login error", e);
                callback.onError("Errore di connessione: " + e.getMessage());
            } finally {
                if (conn != null) conn.disconnect();
            }
        }).start();
    }

    public void register(String username, String email, String password, String birthDate, String serverUrl, String referralCode, AuthCallback callback) {
        final String urlStr = serverUrl + "/auth/register";
        new Thread(() -> {
            HttpURLConnection conn = null;
            try {
                URL url = new URL(urlStr);
                conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setConnectTimeout(15000);
                conn.setReadTimeout(15000);
                conn.setRequestProperty("Content-Type", "application/json");
                conn.setDoOutput(true);

                JSONObject body = new JSONObject();
                body.put("username", username);
                body.put("password", password);
                if (birthDate != null && !birthDate.isEmpty()) {
                    body.put("birth_date", birthDate);
                }
                if (email != null && !email.isEmpty()) {
                    body.put("email", email);
                }
                if (referralCode != null && !referralCode.isEmpty()) {
                    body.put("referral_code", referralCode);
                }

                OutputStream os = conn.getOutputStream();
                os.write(body.toString().getBytes());
                os.close();

                int code = conn.getResponseCode();
                BufferedReader reader = new BufferedReader(new InputStreamReader(
                        code >= 400 ? conn.getErrorStream() : conn.getInputStream()));
                StringBuilder response = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) response.append(line);
                reader.close();

                if (code == 201) {
                    JSONObject json = new JSONObject(response.toString());
                    String accessToken = json.getString("access_token");
                    String refreshToken = json.getString("refresh_token");
                    String persistentToken = json.optString("persistent_token", "");
                    JSONObject user = json.getJSONObject("user");
                    String userId = user.getString("id");
                    String role = user.optString("role", "user");
                    String userEmail = user.optString("email", "");

                    saveTokens(accessToken, refreshToken, userId, username, role, userEmail);
                    if (!persistentToken.isEmpty()) savePersistentToken(persistentToken);
                    callback.onSuccess(accessToken, refreshToken, userId, username, role, userEmail);
                } else {
                    JSONObject err = new JSONObject(response.toString());
                    String msg = err.optString("detail", "Errore registrazione");
                    callback.onError(msg);
                }
            } catch (Exception e) {
                Log.e(TAG, "Register error", e);
                callback.onError("Errore di connessione: " + e.getMessage());
            } finally {
                if (conn != null) conn.disconnect();
            }
        }).start();
    }

    public void refreshToken(String serverUrl, final RefreshCallback callback) {
        final String refreshTok = getRefreshToken();
        if (refreshTok.isEmpty()) {
            callback.onFailure("No refresh token");
            return;
        }

        final String urlStr = serverUrl + "/auth/refresh";
        new Thread(() -> {
            HttpURLConnection conn = null;
            try {
                URL url = new URL(urlStr);
                conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setConnectTimeout(15000);
                conn.setReadTimeout(15000);
                conn.setRequestProperty("Content-Type", "application/json");
                conn.setDoOutput(true);

                JSONObject body = new JSONObject();
                body.put("refresh_token", refreshTok);

                OutputStream os = conn.getOutputStream();
                os.write(body.toString().getBytes());
                os.close();

                int code = conn.getResponseCode();
                if (code == 200) {
                    BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                    StringBuilder response = new StringBuilder();
                    String line;
                    while ((line = reader.readLine()) != null) response.append(line);
                    reader.close();

                    JSONObject json = new JSONObject(response.toString());
                    String newAccess = json.getString("access_token");
                    String newRefresh = json.getString("refresh_token");

                    prefs.edit()
                            .putString(KEY_ACCESS_TOKEN, newAccess)
                            .putString(KEY_REFRESH_TOKEN, newRefresh)
                            .apply();
                    callback.onSuccess(newAccess, newRefresh);
                } else {
                    clear();
                    callback.onFailure("Refresh failed");
                }
            } catch (Exception e) {
                Log.e(TAG, "Refresh error", e);
                callback.onFailure(e.getMessage());
            } finally {
                if (conn != null) conn.disconnect();
            }
        }).start();
    }

    public interface RefreshCallback {
        void onSuccess(String newAccessToken, String newRefreshToken);
        void onFailure(String error);
    }

    public static class HttpResponse {
        public int statusCode;
        public String body;
        public HttpURLConnection connection;
    }

    public HttpResponse requestWithRefresh(String urlStr, String method, String jsonBody, int timeout) throws Exception {
        HttpResponse first = doRequest(urlStr, method, jsonBody, timeout);
        if (first.statusCode == 401 && refreshTokenSync()) {
            HttpResponse second = doRequest(urlStr, method, jsonBody, timeout);
            first.connection.disconnect();
            return second;
        }
        return first;
    }

    private HttpResponse doRequest(String urlStr, String method, String jsonBody, int timeout) throws Exception {
        URL url = new URL(urlStr);
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod(method);
        conn.setConnectTimeout(timeout);
        conn.setReadTimeout(timeout);
        conn.setRequestProperty("Accept", "application/json");
        String token = getAccessToken();
        if (!token.isEmpty()) {
            conn.setRequestProperty("Authorization", "Bearer " + token);
        }
        if (jsonBody != null) {
            conn.setDoOutput(true);
            conn.setRequestProperty("Content-Type", "application/json");
            OutputStream os = conn.getOutputStream();
            os.write(jsonBody.getBytes());
            os.close();
        }
        int code = conn.getResponseCode();
        InputStream is;
        if (code >= 200 && code < 300) {
            is = conn.getInputStream();
        } else {
            is = conn.getErrorStream();
            if (is == null) is = conn.getInputStream();
        }
        BufferedReader reader = new BufferedReader(new InputStreamReader(is != null ? is : new java.io.ByteArrayInputStream(new byte[0])));
        StringBuilder resp = new StringBuilder();
        String line;
        while ((line = reader.readLine()) != null) resp.append(line);
        reader.close();

        HttpResponse result = new HttpResponse();
        result.statusCode = code;
        result.body = resp.toString();
        result.connection = conn;
        return result;
    }

    private boolean refreshTokenSync() {
        String refreshTok = getRefreshToken();
        boolean refreshOk = false;
        if (!refreshTok.isEmpty()) {
            try {
                URL url = new URL(baseUrl + "/auth/refresh");
                HttpURLConnection conn = (HttpURLConnection) url.openConnection();
                conn.setRequestMethod("POST");
                conn.setConnectTimeout(10000);
                conn.setReadTimeout(10000);
                conn.setRequestProperty("Content-Type", "application/json");
                conn.setRequestProperty("Accept", "application/json");
                conn.setDoOutput(true);

                JSONObject body = new JSONObject();
                body.put("refresh_token", refreshTok);
                OutputStream os = conn.getOutputStream();
                os.write(body.toString().getBytes());
                os.close();

                int code = conn.getResponseCode();
                if (code == 200) {
                    BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                    StringBuilder resp = new StringBuilder();
                    // Consume output even on error to avoid leaking sockets
                    String line;
                    while ((line = reader.readLine()) != null) resp.append(line);
                    reader.close();

                    JSONObject json = new JSONObject(resp.toString());
                    String newAccess = json.getString("access_token");
                    String newRefresh = json.getString("refresh_token");
                    prefs.edit()
                            .putString(KEY_ACCESS_TOKEN, newAccess)
                            .putString(KEY_REFRESH_TOKEN, newRefresh)
                            .apply();
                    refreshOk = true;
                }
                conn.disconnect();
            } catch (Exception e) {
                Log.w(TAG, "Refresh token sync failed, trying reauth", e);
            }
        }
        if (refreshOk) return true;

        // Fallback: reauth via persistent token (never expires)
        String persistentTok = getPersistentToken();
        if (persistentTok == null || persistentTok.isEmpty()) return false;
        try {
            URL url = new URL(baseUrl + "/auth/reauth");
            HttpURLConnection conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("POST");
            conn.setConnectTimeout(10000);
            conn.setReadTimeout(10000);
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setRequestProperty("Accept", "application/json");
            conn.setDoOutput(true);

            JSONObject body = new JSONObject();
            body.put("persistent_token", persistentTok);
            OutputStream os = conn.getOutputStream();
            os.write(body.toString().getBytes());
            os.close();

            int code = conn.getResponseCode();
            if (code == 200) {
                BufferedReader reader = new BufferedReader(new InputStreamReader(conn.getInputStream()));
                StringBuilder resp = new StringBuilder();
                String line;
                while ((line = reader.readLine()) != null) resp.append(line);
                reader.close();

                JSONObject json = new JSONObject(resp.toString());
                String newAccess = json.getString("access_token");
                String newRefresh = json.getString("refresh_token");
                prefs.edit()
                        .putString(KEY_ACCESS_TOKEN, newAccess)
                        .putString(KEY_REFRESH_TOKEN, newRefresh)
                        .apply();
                conn.disconnect();
                return true;
            }
            conn.disconnect();
        } catch (Exception e) {
            Log.e(TAG, "Reauth via persistent token failed", e);
        }
        return false;
    }
}
