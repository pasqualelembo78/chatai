package com.intelligame.chatai;

import android.app.Activity;
import android.app.Application;
import android.content.Context;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.widget.FrameLayout;
import android.widget.Toast;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.Map;

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

    // ── Test Ad Unit IDs (Google's official test IDs) ───────────────
    private static final String TEST_BANNER_ID = "ca-app-pub-3940256099942544/6300978111";
    private static final String TEST_INTERSTITIAL_ID = "ca-app-pub-3940256099942544/1033173712";
    private static final String TEST_REWARDED_ID = "ca-app-pub-3940256099942544/5224354917";
    private static final String TEST_APP_OPEN_ID = "ca-app-pub-3940256099942544/9257395921";

    // ── Frequency capping ──────────────────────────────────────────
    private static final long INTERSTITIAL_MIN_INTERVAL_MS = 5 * 60 * 1000; // 5 minutes
    private static final int INTERSTITIAL_MAX_PER_SESSION = 4;
    private static final long APP_OPEN_MIN_INTERVAL_MS = 30 * 60 * 1000; // 30 minutes

    // ── State ───────────────────────────────────────────────────────
    private static AdManager sInstance;

    private InterstitialAd mInterstitialAd;
    private RewardedAd mRewardedAd;
    private AppOpenAd mAppOpenAd;
    private final Map<FrameLayout, AdView> mBannerAds = new HashMap<>();
    private boolean mAdsEnabled = true;
    private boolean mNoAds = false;
    private boolean mInitialized = false;
    private Activity mCurrentActivity;
    private Application mApp;
    private ConsentInformation mConsentInformation;
    private boolean mConsentHandled = false;

    // Frequency capping state
    private long mLastInterstitialShown = 0;
    private int mInterstitialShownThisSession = 0;
    private long mSessionStartTime = 0;

    // App Open ad guard
    private boolean mAppOpenShownThisLaunch = false;
    private long mLastAppOpenShown = 0;

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
     * Mostra il modulo di consensi se richiesto (EEA/Regno Unito). onComplete viene chiamato
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

    // ── Helper: get correct ad unit ID based on debug build ─────────

    private String getBannerId() {
        return isDebugBuild() ? TEST_BANNER_ID : BANNER_ID;
    }

    private String getInterstitialId() {
        return isDebugBuild() ? TEST_INTERSTITIAL_ID : INTERSTITIAL_ID;
    }

    private String getRewardedId() {
        return isDebugBuild() ? TEST_REWARDED_ID : REWARDED_ID;
    }

    private String getAppOpenId() {
        return isDebugBuild() ? TEST_APP_OPEN_ID : APP_OPEN_ID;
    }

    private boolean isDebugBuild() {
        return mApp != null && (mApp.getApplicationInfo().flags & android.content.pm.ApplicationInfo.FLAG_DEBUGGABLE) != 0;
    }

    // ── Banner ──────────────────────────────────────────────────────

    public void showBanner(Activity activity, FrameLayout container) {
        if (!mAdsEnabled || mNoAds || container == null) return;
        if (mBannerAds.containsKey(container)) return;

        AdView adView = new AdView(activity);
        adView.setAdUnitId(getBannerId());
        adView.setAdSize(AdSize.BANNER);
        adView.setAdListener(new com.google.android.gms.ads.AdListener() {
            @Override
            public void onAdLoaded() {
                container.setVisibility(View.VISIBLE);
            }

            @Override
            public void onAdFailedToLoad(LoadAdError error) {
                Log.w("AdManager", "Banner failed to load: " + error.getMessage());
                container.setVisibility(View.GONE);
                removeBanner(container);
            }
        });

        container.removeAllViews();
        container.addView(adView);
        container.setVisibility(View.GONE);
        adView.loadAd(new AdRequest.Builder().build());
        mBannerAds.put(container, adView);
    }

    private void removeBanner(FrameLayout container) {
        AdView ad = mBannerAds.remove(container);
        if (ad != null) {
            ad.destroy();
        }
        if (container != null) {
            container.removeAllViews();
            container.setVisibility(View.GONE);
        }
    }

    public void hideBanner(FrameLayout container) {
        removeBanner(container);
    }

    public void destroyBanner() {
        for (FrameLayout container : new ArrayList<>(mBannerAds.keySet())) {
            removeBanner(container);
        }
    }

    // ── Interstitial with frequency capping ─────────────────────────

    public void preloadInterstitial(Context context) {
        if (!mAdsEnabled || mNoAds) return;
        InterstitialAd.load(context, getInterstitialId(), new AdRequest.Builder().build(),
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
                                Log.w("AdManager", "Interstitial failed to show: " + error.getMessage());
                                mInterstitialAd = null;
                            }
                        });
                    }

                    @Override
                    public void onAdFailedToLoad(@NonNull LoadAdError error) {
                        Log.w("AdManager", "Interstitial failed to load: " + error.getMessage());
                        mInterstitialAd = null;
                    }
                });
    }

    /**
     * Shows interstitial if ready AND frequency capping allows it.
     * Frequency cap: max 4 per session, minimum 5 minutes between shows.
     */
    public void showInterstitialIfReady(Activity activity) {
        long now = System.currentTimeMillis();

        // Reset session counter if session expired (30 minutes)
        if (mSessionStartTime > 0 && now - mSessionStartTime > 30 * 60 * 1000) {
            mSessionStartTime = now;
            mInterstitialShownThisSession = 0;
        }

        // Check frequency caps
        if (mInterstitialShownThisSession >= INTERSTITIAL_MAX_PER_SESSION) {
            Log.d("AdManager", "Interstitial cap reached for this session");
            return;
        }
        if (mLastInterstitialShown > 0 && now - mLastInterstitialShown < INTERSTITIAL_MIN_INTERVAL_MS) {
            Log.d("AdManager", "Interstitial min interval not elapsed");
            return;
        }

        if (mInterstitialAd != null && mAdsEnabled && !mNoAds) {
            mInterstitialAd.show(activity);
            mInterstitialAd = null;
            mLastInterstitialShown = now;
            mInterstitialShownThisSession++;
            if (mSessionStartTime == 0) mSessionStartTime = now;
            Log.d("AdManager", "Interstitial shown (session count: " + mInterstitialShownThisSession + ")");
        }
    }

    // ── Rewarded Video with opt-in confirmation ─────────────────────

    public void preloadRewarded(Context context) {
        if (!mAdsEnabled || mNoAds) return;
        RewardedAd.load(context, getRewardedId(), new AdRequest.Builder().build(),
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
                                Log.w("AdManager", "Rewarded failed to show: " + error.getMessage());
                                mRewardedAd = null;
                            }
                        });
                    }

                    @Override
                    public void onAdFailedToLoad(@NonNull LoadAdError error) {
                        Log.w("AdManager", "Rewarded failed to load: " + error.getMessage());
                        mRewardedAd = null;
                        if (context != null) {
                            new android.os.Handler(android.os.Looper.getMainLooper())
                                    .postDelayed(() -> preloadRewarded(context), 15000);
                        }
                    }
                });
    }

    /**
     * Shows rewarded ad. Caller MUST ensure user explicitly opted in (e.g., via a button labeled
     * "Guarda annuncio per ottenere ricompensa").
     * This method does NOT perform the opt-in dialog itself.
     */
    public void showRewarded(Activity activity, RewardedCallback callback) {
        if (mRewardedAd == null || !mAdsEnabled || mNoAds) {
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
        return mRewardedAd != null && mAdsEnabled && !mNoAds;
    }

    public void setRewardedReadyListener(RewardedReadyListener listener) {
        mRewardedReadyListener = listener;
        if (listener != null && isRewardedReady()) {
            listener.onRewardedReady();
        }
    }

    // ── App Open Ad with launch guard ───────────────────────────────

    public void preloadAppOpen(Context context) {
        if (!mAdsEnabled || mNoAds) return;
        AppOpenAd.load(context, getAppOpenId(), new AdRequest.Builder().build(),
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
                                Log.w("AdManager", "AppOpen failed to show: " + error.getMessage());
                                mAppOpenAd = null;
                            }
                        });
                    }

                    @Override
                    public void onAdFailedToLoad(@NonNull LoadAdError error) {
                        Log.w("AdManager", "AppOpen failed to load: " + error.getMessage());
                        mAppOpenAd = null;
                    }
                });
    }

    /**
     * Shows App Open ad ONLY on true cold start (not on activity recreation).
     * Also respects minimum interval of 30 minutes between shows.
     */
    public void showAppOpenIfReady(Activity activity) {
        long now = System.currentTimeMillis();

        // Guard: don't show on activity recreation (savedInstanceState != null)
        // or if already shown this launch
        if (mAppOpenShownThisLaunch) {
            Log.d("AdManager", "AppOpen already shown this launch");
            return;
        }

        // Guard: minimum interval between app open ads
        if (mLastAppOpenShown > 0 && now - mLastAppOpenShown < APP_OPEN_MIN_INTERVAL_MS) {
            Log.d("AdManager", "AppOpen min interval not elapsed");
            return;
        }

        if (mAppOpenAd != null && mAdsEnabled && !mNoAds) {
            mAppOpenAd.show(activity);
            mAppOpenAd = null;
            mLastAppOpenShown = now;
            mAppOpenShownThisLaunch = true;
            Log.d("AdManager", "AppOpen ad shown");
        }
    }

    // ── Controls ─────────────────────────────────────────────────────

    public void setAdsEnabled(boolean enabled) {
        mAdsEnabled = enabled;
    }

    public boolean isAdsEnabled() {
        return mAdsEnabled;
    }

    /**
     * Se true, tutti gli annunci (banner, interstitial, rewarded, app-open) sono
     * disattivati perché l'utente ha sbloccato "Nessuna pubblicità" con i MVC.
     */
    public void setNoAds(boolean noAds) {
        mNoAds = noAds;
        if (noAds) {
            destroyBanner();
            mInterstitialAd = null;
            mRewardedAd = null;
            mAppOpenAd = null;
        }
    }

    public boolean isNoAds() {
        return mNoAds;
    }

    // ── Lifecycle (track current activity + session) ─────────────────

    @Override
    public void onActivityCreated(@NonNull Activity activity, @Nullable Bundle savedInstanceState) {
        // Reset launch flag when app is truly launched (not recreated)
        if (savedInstanceState == null) {
            mAppOpenShownThisLaunch = false;
        }
    }

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