package com.intelligame.chatai;

import android.app.Activity;
import android.app.Application;
import android.content.Context;
import android.os.Bundle;
import android.view.View;
import android.widget.FrameLayout;
import android.widget.Toast;

import androidx.annotation.NonNull;
import androidx.annotation.Nullable;

import com.google.android.gms.ads.AdError;
import com.google.android.gms.ads.AdRequest;
import com.google.android.gms.ads.AdSize;
import com.google.android.gms.ads.AdView;
import com.google.android.gms.ads.FullScreenContentCallback;
import com.google.android.gms.ads.LoadAdError;
import com.google.android.gms.ads.MobileAds;
import com.google.android.gms.ads.OnUserEarnedRewardListener;
import com.google.android.gms.ads.appopen.AppOpenAd;
import com.google.android.gms.ads.initialization.InitializationStatus;
import com.google.android.gms.ads.initialization.OnInitializationCompleteListener;
import com.google.android.gms.ads.interstitial.InterstitialAd;
import com.google.android.gms.ads.interstitial.InterstitialAdLoadCallback;
import com.google.android.gms.ads.rewarded.RewardedAd;
import com.google.android.gms.ads.rewarded.RewardedAdLoadCallback;
import com.google.android.ump.ConsentInformation;
import com.google.android.ump.ConsentForm;
import com.google.android.ump.ConsentRequestParameters;
import com.google.android.ump.FormError;
import com.google.android.ump.UserMessagingPlatform;

public class AdManager implements Application.ActivityLifecycleCallbacks {

    // ── Real Ad Unit IDs ────────────────────────────────────────────
    private static final String BANNER_ID = "ca-app-pub-2572171530354182/9524398118";
    private static final String INTERSTITIAL_ID = "ca-app-pub-2572171530354182/1578046793";
    private static final String REWARDED_ID = "ca-app-pub-2572171530354182/2958989767";
    private static final String APP_OPEN_ID = "ca-app-pub-2572171530354182/2879098710";

    // ── State ───────────────────────────────────────────────────────
    private static AdManager sInstance;

    private InterstitialAd mInterstitialAd;
    private RewardedAd mRewardedAd;
    private AppOpenAd mAppOpenAd;
    private AdView mBannerAd;
    private boolean mAdsEnabled = true;
    private boolean mInitialized = false;
    private int mMessageCount = 0;
    private Activity mCurrentActivity;
    private Application mApp;
    private ConsentInformation mConsentInformation;
    private boolean mConsentHandled = false;

    // Callback per rewarded ad
    public interface RewardedCallback {
        void onRewardEarned(int amount);
        void onRewardedFailed();
    }

    public interface RewardedReadyListener {
        void onRewardedReady();
    }

    private RewardedCallback mRewardedCallback;
    private RewardedReadyListener mRewardedReadyListener;

    private AdManager() {}

    public static synchronized AdManager getInstance() {
        if (sInstance == null) {
            sInstance = new AdManager();
        }
        return sInstance;
    }

    // ── Initialization ──────────────────────────────────────────────

    public void init(Application app) {
        mApp = app;
        app.registerActivityLifecycleCallbacks(this);
    }

    /**
     * Richiede il consenso (UMP) prima di inizializzare MobileAds e precaricare gli annunci.
     * Mostra il modulo di consenzi se richiesto (EEA/Regno Unito). onComplete viene chiamato
     * al termine della gestione del consenso (modulo chiuso o non necessario).
     */
    public void initConsent(final Activity activity, final Runnable onComplete) {
        if (mConsentHandled) {
            if (onComplete != null) onComplete.run();
            return;
        }
        if (!mAdsEnabled || mApp == null) {
            mConsentHandled = true;
            if (onComplete != null) onComplete.run();
            return;
        }

        mConsentInformation = UserMessagingPlatform.getConsentInformation(mApp);

        ConsentRequestParameters params = new ConsentRequestParameters.Builder()
                .setTagForUnderAgeOfConsent(false)
                .build();

        mConsentInformation.requestConsentInfoUpdate(activity, params,
                new ConsentInformation.OnConsentInfoUpdateSuccessListener() {
                    @Override
                    public void onConsentInfoUpdateSuccess() {
                        showConsentFormIfRequired(activity, onComplete);
                    }
                },
                new ConsentInformation.OnConsentInfoUpdateFailureListener() {
                    @Override
                    public void onConsentInfoUpdateFailure(FormError formError) {
                        // Procedi comunque: gli annunci saranno non personalizzati di default
                        finishConsent(onComplete);
                    }
                });
    }

    private void showConsentFormIfRequired(final Activity activity, final Runnable onComplete) {
        UserMessagingPlatform.loadAndShowConsentFormIfRequired(activity,
                new ConsentForm.OnConsentFormDismissedListener() {
                    @Override
                    public void onConsentFormDismissed(FormError formError) {
                        finishConsent(onComplete);
                    }
                });
    }

    private void finishConsent(Runnable onComplete) {
        mConsentHandled = true;
        initMobileAds();
        if (onComplete != null) onComplete.run();
    }

    /**
     * @return true se l'utente deve poter riaprire il modulo privacy (EEA/Regno Unito, stato REQUIRED).
     */
    public boolean isPrivacyOptionsRequired() {
        return mConsentInformation != null
                && mConsentInformation.getPrivacyOptionsRequirementStatus()
                    == ConsentInformation.PrivacyOptionsRequirementStatus.REQUIRED;
    }

    /**
     * Mostra il modulo "Gestisci consenso" per permettere all'utente di modificare/revocare
     * le scelte sulla personalizzazione degli annunci.
     */
    public void showPrivacyOptionsForm(final Activity activity, final Runnable onComplete) {
        if (mConsentInformation == null) {
            if (onComplete != null) onComplete.run();
            return;
        }
        if (mConsentInformation.getPrivacyOptionsRequirementStatus()
                != ConsentInformation.PrivacyOptionsRequirementStatus.REQUIRED) {
            Toast.makeText(activity,
                    "La gestione del consenso non è al momento disponibile.",
                    Toast.LENGTH_SHORT).show();
            if (onComplete != null) onComplete.run();
            return;
        }
        UserMessagingPlatform.loadConsentForm(
                activity,
                new UserMessagingPlatform.OnConsentFormLoadSuccessListener() {
                    @Override
                    public void onConsentFormLoadSuccess(ConsentForm form) {
                        form.show(activity, new ConsentForm.OnConsentFormDismissedListener() {
                            @Override
                            public void onConsentFormDismissed(FormError formError) {
                                if (formError != null) {
                                    Toast.makeText(activity,
                                            "Impossibile aprire il modulo consenso.",
                                            Toast.LENGTH_SHORT).show();
                                }
                                if (onComplete != null) onComplete.run();
                            }
                        });
                    }
                },
                new UserMessagingPlatform.OnConsentFormLoadFailureListener() {
                    @Override
                    public void onConsentFormLoadFailure(FormError formError) {
                        Toast.makeText(activity,
                                "Impossibile caricare il modulo consenso.",
                                Toast.LENGTH_SHORT).show();
                        if (onComplete != null) onComplete.run();
                    }
                });
    }

    private void initMobileAds() {
        if (mInitialized || mApp == null) return;
        mInitialized = true;

        MobileAds.initialize(mApp, new OnInitializationCompleteListener() {
            @Override
            public void onInitializationComplete(InitializationStatus status) {}
        });

        // Preload ads
        preloadInterstitial(mApp);
        preloadRewarded(mApp);
        preloadAppOpen(mApp);
    }

    // ── Banner ──────────────────────────────────────────────────────

    public void showBanner(Activity activity, FrameLayout container) {
        if (!mAdsEnabled || mBannerAd != null) return;

        mBannerAd = new AdView(activity);
        mBannerAd.setAdUnitId(BANNER_ID);
        mBannerAd.setAdSize(AdSize.BANNER);
        mBannerAd.setAdListener(new com.google.android.gms.ads.AdListener() {
            @Override
            public void onAdLoaded() {
                container.setVisibility(View.VISIBLE);
            }

            @Override
            public void onAdFailedToLoad(LoadAdError error) {
                container.setVisibility(View.GONE);
                mBannerAd = null;
            }
        });

        container.removeAllViews();
        container.addView(mBannerAd);
        mBannerAd.loadAd(new AdRequest.Builder().build());
    }

    public void hideBanner(FrameLayout container) {
        if (mBannerAd != null) {
            mBannerAd.destroy();
            mBannerAd = null;
        }
        if (container != null) {
            container.removeAllViews();
            container.setVisibility(View.GONE);
        }
    }

    public void destroyBanner() {
        if (mBannerAd != null) {
            mBannerAd.destroy();
            mBannerAd = null;
        }
    }

    // ── Interstitial (app open / close / ogni N messaggi) ───────────

    public void preloadInterstitial(Context context) {
        if (!mAdsEnabled) return;
        InterstitialAd.load(context, INTERSTITIAL_ID, new AdRequest.Builder().build(),
                new InterstitialAdLoadCallback() {
                    @Override
                    public void onAdLoaded(@NonNull InterstitialAd ad) {
                        mInterstitialAd = ad;
                        mInterstitialAd.setFullScreenContentCallback(new FullScreenContentCallback() {
                            @Override
                            public void onAdDismissedFullScreenContent() {
                                mInterstitialAd = null;
                                preloadInterstitial(context);
                            }

                            @Override
                            public void onAdFailedToShowFullScreenContent(AdError error) {
                                mInterstitialAd = null;
                            }
                        });
                    }

                    @Override
                    public void onAdFailedToLoad(@NonNull LoadAdError error) {
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
        if (mMessageCount >= 8) {
            mMessageCount = 0;
            showInterstitialIfReady(activity);
        }
    }

    // ── Rewarded Video ──────────────────────────────────────────────

    public void preloadRewarded(Context context) {
        if (!mAdsEnabled) return;
        RewardedAd.load(context, REWARDED_ID, new AdRequest.Builder().build(),
                new RewardedAdLoadCallback() {
                    @Override
                    public void onAdLoaded(@NonNull RewardedAd ad) {
                        mRewardedAd = ad;
                        if (mRewardedReadyListener != null) {
                            mRewardedReadyListener.onRewardedReady();
                        }
                        mRewardedAd.setFullScreenContentCallback(new FullScreenContentCallback() {
                            @Override
                            public void onAdDismissedFullScreenContent() {
                                mRewardedAd = null;
                                preloadRewarded(context);
                            }

                            @Override
                            public void onAdFailedToShowFullScreenContent(AdError error) {
                                mRewardedAd = null;
                            }
                        });
                    }

                    @Override
                    public void onAdFailedToLoad(@NonNull LoadAdError error) {
                        mRewardedAd = null;
                        if (context != null) {
                            new android.os.Handler(android.os.Looper.getMainLooper())
                                    .postDelayed(() -> preloadRewarded(context), 15000);
                        }
                    }
                });
    }

    public void showRewarded(Activity activity, RewardedCallback callback) {
        if (mRewardedAd == null || !mAdsEnabled) {
            if (callback != null) callback.onRewardedFailed();
            return;
        }

        mRewardedAd.show(activity, new OnUserEarnedRewardListener() {
            @Override
            public void onUserEarnedReward(@NonNull com.google.android.gms.ads.rewarded.RewardItem reward) {
                if (callback != null) {
                    callback.onRewardEarned(reward.getAmount());
                }
            }
        });
        mRewardedAd = null;
    }

    public boolean isRewardedReady() {
        return mRewardedAd != null && mAdsEnabled;
    }

    public void setRewardedReadyListener(RewardedReadyListener listener) {
        mRewardedReadyListener = listener;
        if (listener != null && isRewardedReady()) {
            listener.onRewardedReady();
        }
    }

    // ── App Open Ad ─────────────────────────────────────────────────

    public void preloadAppOpen(Context context) {
        if (!mAdsEnabled) return;
        AppOpenAd.load(context, APP_OPEN_ID, new AdRequest.Builder().build(),
                new AppOpenAd.AppOpenAdLoadCallback() {
                    @Override
                    public void onAdLoaded(@NonNull AppOpenAd ad) {
                        mAppOpenAd = ad;
                        mAppOpenAd.setFullScreenContentCallback(new FullScreenContentCallback() {
                            @Override
                            public void onAdDismissedFullScreenContent() {
                                mAppOpenAd = null;
                                preloadAppOpen(context);
                            }

                            @Override
                            public void onAdFailedToShowFullScreenContent(AdError error) {
                                mAppOpenAd = null;
                            }
                        });
                    }

                    @Override
                    public void onAdFailedToLoad(@NonNull LoadAdError error) {
                        mAppOpenAd = null;
                    }
                });
    }

    public void showAppOpenIfReady(Activity activity) {
        if (mAppOpenAd != null && mAdsEnabled) {
            mAppOpenAd.show(activity);
            mAppOpenAd = null;
        }
    }

    // ── Controls ────────────────────────────────────────────────────

    public void setAdsEnabled(boolean enabled) {
        mAdsEnabled = enabled;
    }

    public boolean isAdsEnabled() {
        return mAdsEnabled;
    }

    // ── Lifecycle (track current activity) ──────────────────────────

    @Override
    public void onActivityCreated(@NonNull Activity activity, @Nullable Bundle savedInstanceState) {}

    @Override
    public void onActivityStarted(@NonNull Activity activity) {
        mCurrentActivity = activity;
    }

    @Override
    public void onActivityResumed(@NonNull Activity activity) {
        mCurrentActivity = activity;
    }

    @Override
    public void onActivityPaused(@NonNull Activity activity) {}

    @Override
    public void onActivityStopped(@NonNull Activity activity) {}

    @Override
    public void onActivitySaveInstanceState(@NonNull Activity activity, @NonNull Bundle outState) {}

    @Override
    public void onActivityDestroyed(@NonNull Activity activity) {
        if (mCurrentActivity == activity) {
            mCurrentActivity = null;
        }
    }

    @Nullable
    public Activity getCurrentActivity() {
        return mCurrentActivity;
    }
}
