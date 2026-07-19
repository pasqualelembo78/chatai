package com.intelligame.chatai;

import android.content.Context;
import android.content.SharedPreferences;
import android.util.Log;

import androidx.security.crypto.EncryptedSharedPreferences;
import androidx.security.crypto.MasterKey;

import java.util.HashSet;
import java.util.Set;

public class PrefsManager {

    private static final String NAME = "ai_roleplay_prefs_encrypted";
    private static final String KEY_USERNAME = "username";
    private static final String KEY_CHARACTER = "character_id";
    private static final String KEY_PROVIDER = "provider";
    private static final String KEY_MODEL = "model";
    private static final String KEY_SERVER_URL = "server_url";
    private static final String KEY_PROVIDERS_WITH_KEYS = "providers_with_keys";
    private static final String KEY_LAST_CHARACTER_POS = "last_character_pos";
    private static final String KEY_PRIVACY_ACCEPTED = "privacy_accepted";
    private static final String KEY_TOS_ACCEPTED = "tos_accepted";
    private static final String KEY_BLOCKED_USERS = "blocked_users";
    private static final String KEY_API_KEY_PREFIX = "api_key_";
    private static final String KEY_MVC_ONBOARDED = "mvc_onboarded";

    private static final String DEFAULT_SERVER_URL = "https://82.165.218.56";
    private static final String DEFAULT_CHARACTER_ID = "ginecologa";

    private final SharedPreferences prefs;

    public PrefsManager(Context context) {
        try {
            MasterKey masterKey = new MasterKey.Builder(context)
                    .setKeyScheme(MasterKey.KeyScheme.AES256_GCM)
                    .build();
            this.prefs = EncryptedSharedPreferences.create(
                    context,
                    NAME,
                    masterKey,
                    EncryptedSharedPreferences.PrefKeyEncryptionScheme.AES256_SIV,
                    EncryptedSharedPreferences.PrefValueEncryptionScheme.AES256_GCM
            );
        } catch (Exception e) {
            Log.e("PrefsManager", "EncryptedSharedPreferences unavailable", e);
            throw new SecurityException("EncryptedSharedPreferences is required for secure storage", e);
        }
    }

    public String getUsername() {
        return prefs.getString(KEY_USERNAME, "");
    }

    public void setUsername(String username) {
        prefs.edit().putString(KEY_USERNAME, username).apply();
    }

    public String getCharacterId() {
        return prefs.getString(KEY_CHARACTER, DEFAULT_CHARACTER_ID);
    }

    public void setCharacterId(String id) {
        prefs.edit().putString(KEY_CHARACTER, id).apply();
    }

    public int getLastCharacterPosition() {
        return prefs.getInt(KEY_LAST_CHARACTER_POS, 0);
    }

    public void setLastCharacterPosition(int pos) {
        prefs.edit().putInt(KEY_LAST_CHARACTER_POS, pos).apply();
    }

    public String getProvider() {
        return prefs.getString(KEY_PROVIDER, "auto");
    }

    public void setProvider(String provider) {
        prefs.edit().putString(KEY_PROVIDER, provider).apply();
    }

    public String getModel() {
        return prefs.getString(KEY_MODEL, "auto");
    }

    public void setModel(String model) {
        prefs.edit().putString(KEY_MODEL, model).apply();
    }

    public String getServerUrl() {
        return prefs.getString(KEY_SERVER_URL, DEFAULT_SERVER_URL);
    }

    public void setServerUrl(String url) {
        prefs.edit().putString(KEY_SERVER_URL, url).apply();
    }

    public boolean isTosAccepted() {
        return prefs.getBoolean(KEY_TOS_ACCEPTED, false);
    }

    public void setTosAccepted(boolean accepted) {
        prefs.edit().putBoolean(KEY_TOS_ACCEPTED, accepted).apply();
    }

    public Set<String> getBlockedUsers() {
        return new HashSet<>(prefs.getStringSet(KEY_BLOCKED_USERS, new HashSet<String>()));
    }

    public void addBlockedUser(String userId) {
        Set<String> set = getBlockedUsers();
        set.add(userId);
        prefs.edit().putStringSet(KEY_BLOCKED_USERS, set).apply();
    }

    public void removeBlockedUser(String userId) {
        Set<String> set = getBlockedUsers();
        set.remove(userId);
        prefs.edit().putStringSet(KEY_BLOCKED_USERS, set).apply();
    }

    public boolean isUserBlocked(String userId) {
        return getBlockedUsers().contains(userId);
    }

    public Set<String> getProvidersWithKeys() {
        return prefs.getStringSet(KEY_PROVIDERS_WITH_KEYS, new HashSet<String>());
    }

    public void setProviderHasKey(String providerId, boolean hasKey) {
        Set<String> keys = new HashSet<>(getProvidersWithKeys());
        if (hasKey) {
            keys.add(providerId);
        } else {
            keys.remove(providerId);
        }
        prefs.edit().putStringSet(KEY_PROVIDERS_WITH_KEYS, keys).apply();
    }

    public boolean providerHasKey(String providerId) {
        return getProvidersWithKeys().contains(providerId);
    }

    public String getApiKey(String providerId) {
        return prefs.getString(KEY_API_KEY_PREFIX + providerId, "");
    }

    public void setApiKey(String providerId, String key) {
        prefs.edit().putString(KEY_API_KEY_PREFIX + providerId, key).apply();
        setProviderHasKey(providerId, !key.isEmpty());
    }

    public boolean hasUsername() {
        return !getUsername().isEmpty();
    }

    public boolean isPrivacyAccepted() {
        return prefs.getBoolean(KEY_PRIVACY_ACCEPTED, false);
    }

    public void setPrivacyAccepted(boolean accepted) {
        prefs.edit().putBoolean(KEY_PRIVACY_ACCEPTED, accepted).apply();
    }

    public boolean isMvcOnboarded() {
        return prefs.getBoolean(KEY_MVC_ONBOARDED, false);
    }

    public void setMvcOnboarded(boolean onboarded) {
        prefs.edit().putBoolean(KEY_MVC_ONBOARDED, onboarded).apply();
    }

    public void clearAll() {
        prefs.edit().clear().apply();
    }
}