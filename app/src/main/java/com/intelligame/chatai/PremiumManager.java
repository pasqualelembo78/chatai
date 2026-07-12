package com.intelligame.chatai;

import android.app.Activity;
import android.content.Context;

import com.android.billingclient.api.BillingClient;
import com.android.billingclient.api.BillingClientStateListener;
import com.android.billingclient.api.BillingFlowParams;
import com.android.billingclient.api.BillingResult;
import com.android.billingclient.api.Purchase;
import com.android.billingclient.api.PurchasesUpdatedListener;
import com.android.billingclient.api.SkuDetails;
import com.android.billingclient.api.SkuDetailsParams;

import java.util.List;

public class PremiumManager implements PurchasesUpdatedListener {

    private BillingClient mBillingClient;
    private boolean mIsPremium = false;
    private String mSku = "chatai_premium_monthly";
    private boolean mInitialized = false;

    public PremiumManager(Context context) {
        mBillingClient = BillingClient.newBuilder(context)
                .setListener(this)
                .enablePendingPurchases()
                .build();
    }

    public void init(Context context) {
        if (mInitialized) return;
        mInitialized = true;

        mBillingClient.startConnection(new BillingClientStateListener() {
            @Override
            public void onBillingSetupFinished(BillingResult billingResult) {
                if (billingResult.getResponseCode() == BillingClient.BillingResponseCode.OK) {
                    checkExistingPurchases();
                }
            }

            @Override
            public void onBillingServiceDisconnected() {}
        });
    }

    private void checkExistingPurchases() {
        if (!mBillingClient.isReady()) return;

        mBillingClient.queryPurchasesAsync(BillingClient.SkuType.SUBS, (billingResult, purchasesList) -> {
            if (billingResult.getResponseCode() == BillingClient.BillingResponseCode.OK) {
                for (Purchase purchase : purchasesList) {
                    if (purchase.getPurchaseState() == Purchase.PurchaseState.PURCHASED) {
                        mIsPremium = true;
                        return;
                    }
                }
            }
            mIsPremium = false;
        });
    }

    public boolean isPremium() {
        return mIsPremium;
    }

    public void launchSubscriptionFlow(Activity activity) {
        if (!mBillingClient.isReady()) return;

        SkuDetailsParams params = SkuDetailsParams.newBuilder()
                .setSkusList(List.of(mSku))
                .setType(BillingClient.SkuType.SUBS)
                .build();

        mBillingClient.querySkuDetailsAsync(params, (billingResult, skuDetailsList) -> {
            if (billingResult.getResponseCode() == BillingClient.BillingResponseCode.OK && skuDetailsList != null) {
                for (SkuDetails skuDetails : skuDetailsList) {
                    if (skuDetails.getSku().equals(mSku)) {
                        BillingFlowParams flowParams = BillingFlowParams.newBuilder()
                                .setSkuDetails(skuDetails)
                                .build();
                        mBillingClient.launchBillingFlow(activity, flowParams);
                        return;
                    }
                }
            }
        });
    }

    @Override
    public void onPurchasesUpdated(BillingResult billingResult, List<Purchase> purchases) {
        if (billingResult.getResponseCode() == BillingClient.BillingResponseCode.OK && purchases != null) {
            for (Purchase purchase : purchases) {
                if (purchase.getPurchaseState() == Purchase.PurchaseState.PURCHASED) {
                    mIsPremium = true;
                    // Disable ads
                    AdManager.getInstance().setAdsEnabled(false);
                    return;
                }
            }
        }
    }

    public void destroy() {
        if (mBillingClient != null && mBillingClient.isReady()) {
            mBillingClient.endConnection();
        }
    }
}
