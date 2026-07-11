package com.intelligame.chatai;

import android.content.Context;
import android.widget.ImageView;

import com.bumptech.glide.Glide;
import com.bumptech.glide.load.engine.DiskCacheStrategy;
import com.google.android.material.imageview.ShapeableImageView;

public class AvatarLoader {

    public static void loadAvatar(Context context, String avatarId,
                                   ShapeableImageView imageView,
                                   android.widget.TextView emojiView,
                                   String emojiFallback) {
        if (avatarId == null || avatarId.isEmpty()) {
            showEmoji(imageView, emojiView, emojiFallback);
            return;
        }

        PrefsManager prefs = new PrefsManager(context);
        String url = prefs.getServerUrl() + "/avatars/" + avatarId;

        Glide.with(context)
            .load(url)
            .diskCacheStrategy(DiskCacheStrategy.ALL)
            .placeholder(android.R.color.transparent)
            .error(R.drawable.ic_launcher)
            .into(imageView);

        imageView.setVisibility(android.view.View.VISIBLE);
        if (emojiView != null) {
            emojiView.setVisibility(android.view.View.GONE);
        }
    }

    public static void loadAvatarIntoImageView(Context context, String avatarId,
                                                ImageView imageView) {
        if (avatarId == null || avatarId.isEmpty()) return;

        PrefsManager prefs = new PrefsManager(context);
        String url = prefs.getServerUrl() + "/avatars/" + avatarId;

        Glide.with(context)
            .load(url)
            .diskCacheStrategy(DiskCacheStrategy.ALL)
            .placeholder(android.R.color.transparent)
            .error(android.R.color.transparent)
            .into(imageView);
    }

    private static void showEmoji(ShapeableImageView imageView,
                                   android.widget.TextView emojiView,
                                   String emoji) {
        imageView.setVisibility(android.view.View.GONE);
        if (emojiView != null) {
            emojiView.setVisibility(android.view.View.VISIBLE);
            emojiView.setText(emoji != null && !emoji.isEmpty() ? emoji : "👤");
        }
    }
}
