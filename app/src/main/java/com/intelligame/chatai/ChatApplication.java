package com.intelligame.chatai;

import android.app.Application;
import android.os.Handler;
import android.os.Looper;

import io.socket.client.IO;
import io.socket.client.Socket;

import java.net.URISyntaxException;
import java.util.HashMap;
import java.util.Map;

public class ChatApplication extends Application {

    private Socket mSocket;
    private String mCurrentUrl;
    private PrefsManager mPrefs;
    private AuthManager mAuth;
    private LocalDatabaseHelper mLocalDb;
    private PremiumManager mPremiumManager;

    @Override
    public void onCreate() {
        super.onCreate();
        mPrefs = new PrefsManager(this);
        mLocalDb = new LocalDatabaseHelper(this);
        mCurrentUrl = mPrefs.getServerUrl();
        mAuth = new AuthManager(this, mCurrentUrl);

        new Thread(() -> {
            mPremiumManager = new PremiumManager(ChatApplication.this);
            mPremiumManager.init(ChatApplication.this);
        }).start();

        AdManager.getInstance().init(this);
    }

    public LocalDatabaseHelper getLocalDb() {
        return mLocalDb;
    }

    public PremiumManager getPremiumManager() {
        return mPremiumManager;
    }

    public AdManager getAdManager() {
        return AdManager.getInstance();
    }

    public AuthManager getAuthManager() {
        return mAuth;
    }

    public void connectWithAuth(String url) {
        if (mSocket != null && mSocket.connected()) {
            mSocket.disconnect();
            mSocket.off();
        }
        try {
            IO.Options opts = new IO.Options();
            opts.forceNew = true;
            opts.reconnection = true;
            opts.reconnectionAttempts = 10;
            opts.reconnectionDelay = 1000;

            String token = mAuth.getAccessToken();
            if (!token.isEmpty()) {
                Map<String, String> authMap = new HashMap<>();
                authMap.put("token", token);
                opts.auth = authMap;
            }

            mSocket = IO.socket(url, opts);
            mCurrentUrl = url;
            mSocket.connect();
        } catch (URISyntaxException e) {
            throw new RuntimeException(e);
        }
    }

    public void reconnect(String newUrl) {
        if (mSocket != null) {
            mSocket.disconnect();
            mSocket.off();
        }
        mPrefs.setServerUrl(newUrl);
        mAuth = new AuthManager(this, newUrl);
        connectWithAuth(newUrl);
    }

    public Socket getSocket() {
        if (mSocket == null) {
            connectWithAuth(mCurrentUrl);
        } else if (!mSocket.connected()) {
            mSocket.connect();
        }
        return mSocket;
    }

    public String getCurrentUrl() {
        return mCurrentUrl;
    }

    public PrefsManager getPrefs() {
        return mPrefs;
    }
}
