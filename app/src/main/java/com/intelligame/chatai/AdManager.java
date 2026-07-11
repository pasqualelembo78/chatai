package com.intelligame.chatai;

import android.app.Activity;
import android.content.Context;
import android.view.View;
import android.widget.FrameLayout;

import com.google.android.gms.ads.AdError;
import com.google.android.gms.ads.AdRequest;
import com.google.android.gms.ads.AdSize;
import com.google.android.gms.ads.AdView;
import com.google.android.gms.ads.FullScreenContentCallback;
import com.google.android.gms.ads.LoadAdError;
import com.google.android.gms.ads.MobileAds;
import com.google.android.gms.ads.initialization.InitializationStatus;
import com.google.android.gms.ads.initialization.OnInitializationCompleteListener;
import com.google.android.gms.ads.interstitial.InterstitialAd;
import com.google.android.gms.ads.interstitial.InterstitialAdLoadCallback;

public class AdManager {

    private static final String BANNER_TEST_ID = "ca-app-pub-3940256099942544/6300978111";
    private static final String INTERSTITIAL_TEST_ID = "ca-app-pub-3940256099942544/1033173712";

    private InterstitialAd mInterstitialAd;
    private AdView mBannerAd;
    private int mMessageCount = 0;
    private boolean mAdsEnabled = true;

    public AdManager() {}

    public void init(Context context) {
        MobileAds.initialize(context, new OnInitializationCompleteListener() {
            @Override
            public void onInitializationComplete(InitializationStatus initializationStatus) {}
        });
    }

    public void createBanner(Activity activity, FrameLayout adContainer) {
        if (mBannerAd != null) {
            mBannerAd.destroy();
        }
        mBannerAd = new AdView(activity);
        mBannerAd.setAdSize(AdSize.BANNER);
        mBannerAd.setAdUnitId(BANNER_TEST_ID);
        adContainer.removeAllViews();
        adContainer.addView(mBannerAd);
        AdRequest adRequest = new AdRequest.Builder().build();
        mBannerAd.loadAd(adRequest);
    }

    public void destroyBanner() {
        if (mBannerAd != null) {
            mBannerAd.destroy();
            mBannerAd = null;
        }
    }

    public void loadInterstitial(Activity activity) {
        if (!mAdsEnabled) return;
        AdRequest adRequest = new AdRequest.Builder().build();
        InterstitialAd.load(activity, INTERSTITIAL_TEST_ID, adRequest,
                new InterstitialAdLoadCallback() {
                    @Override
                    public void onAdLoaded(InterstitialAd interstitialAd) {
                        mInterstitialAd = interstitialAd;
                    }

                    @Override
                    public void onAdFailedToLoad(LoadAdError loadAdError) {
                        mInterstitialAd = null;
                    }
                });
    }

    public void showInterstitialIfReady(Activity activity) {
        if (mInterstitialAd != null && mAdsEnabled) {
            mInterstitialAd.show(activity);
            mInterstitialAd = null;
        }
    }

    public void onMessageSent(Activity activity) {
        if (!mAdsEnabled) return;
        mMessageCount++;
        if (mMessageCount >= 10) {
            mMessageCount = 0;
            showInterstitialIfReady(activity);
            loadInterstitial(activity);
        }
    }

    public void setAdsEnabled(boolean enabled) {
        mAdsEnabled = enabled;
    }
}
