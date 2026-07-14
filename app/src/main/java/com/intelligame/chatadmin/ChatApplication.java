package com.intelligame.chatadmin;

import android.app.Application;

public class ChatApplication extends Application {

    private PrefsManager mPrefs;
    private AuthManager mAuth;

    @Override
    public void onCreate() {
        super.onCreate();
        mPrefs = new PrefsManager(this);
        mAuth = new AuthManager(this, mPrefs.getServerUrl());
    }

    public AuthManager getAuthManager() {
        return mAuth;
    }

    public PrefsManager getPrefs() {
        return mPrefs;
    }

    public String getCurrentUrl() {
        return mPrefs.getServerUrl();
    }
}
