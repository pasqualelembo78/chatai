package com.intelligame.chatai;

import android.content.Context;
import android.content.SharedPreferences;

import java.util.HashSet;
import java.util.Set;

public class PrefsManager {

    private static final String NAME = "ai_roleplay_prefs";
    private static final String KEY_USERNAME = "username";
    private static final String KEY_CHARACTER = "character_id";
    private static final String KEY_PROVIDER = "provider";
    private static final String KEY_MODEL = "model";
    private static final String KEY_SERVER_URL = "server_url";
    private static final String KEY_PROVIDERS_WITH_KEYS = "providers_with_keys";
    private static final String KEY_LAST_CHARACTER_POS = "last_character_pos";
    private static final String KEY_PRIVACY_ACCEPTED = "privacy_accepted";
    private static final String KEY_SHOW_ADULT = "show_adult";
    private static final String KEY_API_KEY_PREFIX = "api_key_";

    private static final String DEFAULT_SERVER_URL = "http://82.165.218.56:5000";

    private final SharedPreferences prefs;

    public PrefsManager(Context context) {
        prefs = context.getSharedPreferences(NAME, Context.MODE_PRIVATE);
    }

    public String getUsername() {
        return prefs.getString(KEY_USERNAME, "");
    }

    public void setUsername(String username) {
        prefs.edit().putString(KEY_USERNAME, username).apply();
    }

    public String getCharacterId() {
        return prefs.getString(KEY_CHARACTER, "ginecologa");
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

    public boolean getShowAdult() {
        return prefs.getBoolean(KEY_SHOW_ADULT, false);
    }

    public void setShowAdult(boolean show) {
        prefs.edit().putBoolean(KEY_SHOW_ADULT, show).apply();
    }

    public void setAdultBirthYear(int year) {
        prefs.edit().putInt("adult_birth_year", year).apply();
    }

    public int getAdultBirthYear() {
        return prefs.getInt("adult_birth_year", 0);
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
}
