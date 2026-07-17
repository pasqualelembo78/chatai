package com.intelligame.chatai;

import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.app.Activity;
import android.view.WindowManager;
import android.widget.VideoView;

public class SplashActivity extends Activity {

    private static final int SPLASH_DURATION_MS = 5000;

    private boolean mCanProceed = false;
    private boolean mConsentDone = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);

        getWindow().setFlags(
            WindowManager.LayoutParams.FLAG_FULLSCREEN,
            WindowManager.LayoutParams.FLAG_FULLSCREEN
        );

        setContentView(R.layout.activity_splash);

        VideoView videoView = findViewById(R.id.splash_video);
        videoView.setVideoURI(Uri.parse("android.resource://" + getPackageName() + "/" + R.raw.splash));
        videoView.setOnPreparedListener(mp -> {
            mp.setLooping(false);
            videoView.start();
        });

        ((ChatApplication) getApplication()).getAdManager().initConsent(this, new Runnable() {
            @Override
            public void run() {
                mConsentDone = true;
                maybeProceed();
            }
        });

        new Handler(Looper.getMainLooper()).postDelayed(() -> {
            mCanProceed = true;
            maybeProceed();
        }, SPLASH_DURATION_MS);
    }

    private void maybeProceed() {
        if (mCanProceed && mConsentDone && !isFinishing()) {
            startActivity(new Intent(SplashActivity.this, MainActivity.class));
            finish();
            overridePendingTransition(android.R.anim.fade_in, android.R.anim.fade_out);
        }
    }
}
