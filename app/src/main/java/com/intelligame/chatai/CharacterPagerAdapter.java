package com.intelligame.chatai;

import android.content.Context;
import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageButton;
import android.widget.ProgressBar;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;

import com.google.android.material.button.MaterialButton;
import com.google.android.material.imageview.ShapeableImageView;

import java.util.HashSet;
import java.util.List;
import java.util.Set;

public class CharacterPagerAdapter extends RecyclerView.Adapter<CharacterPagerAdapter.PageViewHolder> {

    public interface OnPageClickListener {
        void onCharacterClick(HomeFragment.CharacterItem character);
        void onFavoriteClick(HomeFragment.CharacterItem character, boolean isFavorite);
    }

    private final List<HomeFragment.CharacterItem> characters;
    private final OnPageClickListener listener;
    private final Set<String> favoriteIds = new HashSet<>();
    private boolean showLoading = false;

    public CharacterPagerAdapter(List<HomeFragment.CharacterItem> characters, OnPageClickListener listener) {
        this.characters = characters;
        this.listener = listener;
    }

    public void setFavoriteIds(Set<String> ids) {
        favoriteIds.clear();
        if (ids != null) favoriteIds.addAll(ids);
        notifyDataSetChanged();
    }

    public void toggleFavorite(String characterId) {
        if (favoriteIds.contains(characterId)) {
            favoriteIds.remove(characterId);
        } else {
            favoriteIds.add(characterId);
        }
        notifyDataSetChanged();
    }

    public void setShowLoading(boolean show) {
        if (this.showLoading != show) {
            this.showLoading = show;
            if (show && !characters.isEmpty()) {
                notifyItemChanged(characters.size() - 1);
            }
        }
    }

    @Override
    public int getItemCount() {
        return characters.size();
    }

    public HomeFragment.CharacterItem getItem(int position) {
        if (position >= 0 && position < characters.size()) {
            return characters.get(position);
        }
        return null;
    }

    @NonNull
    @Override
    public PageViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        View view = LayoutInflater.from(parent.getContext())
                .inflate(R.layout.item_character_fullscreen, parent, false);
        return new PageViewHolder(view);
    }

    @Override
    public void onBindViewHolder(@NonNull PageViewHolder holder, int position) {
        HomeFragment.CharacterItem character = characters.get(position);
        Context ctx = holder.itemView.getContext();

        AvatarLoader.loadAvatar(ctx, character.avatarImage, holder.avatarImage, holder.avatarEmoji, character.emoji);
        holder.name.setText(character.name);
        holder.description.setText(character.description);
        holder.tags.setText(character.getTagsString());
        holder.conversations.setText(character.getConversationsString() + " chat");

        boolean isFav = favoriteIds.contains(character.id);
        holder.favoriteButton.setImageResource(isFav ? R.drawable.ic_favorite_filled : R.drawable.ic_favorite_border);
        holder.favoriteButton.setColorFilter(isFav ? 0xFFFF0000 : ctx.getColor(R.color.on_surface_dim));

        holder.favoriteButton.setOnClickListener(v -> {
            boolean newState = !favoriteIds.contains(character.id);
            if (newState) {
                favoriteIds.add(character.id);
            } else {
                favoriteIds.remove(character.id);
            }
            holder.favoriteButton.setImageResource(newState ? R.drawable.ic_favorite_filled : R.drawable.ic_favorite_border);
            holder.favoriteButton.setColorFilter(newState ? 0xFFFF0000 : ctx.getColor(R.color.on_surface_dim));
            listener.onFavoriteClick(character, newState);
        });

        holder.chatButton.setOnClickListener(v -> listener.onCharacterClick(character));
        holder.itemView.setOnClickListener(v -> listener.onCharacterClick(character));

        boolean isLoadingPage = showLoading && position == characters.size() - 1;
        holder.loadingIndicator.setVisibility(isLoadingPage ? View.VISIBLE : View.GONE);
    }

    static class PageViewHolder extends RecyclerView.ViewHolder {
        ShapeableImageView avatarImage;
        TextView avatarEmoji;
        TextView name;
        TextView description;
        TextView tags;
        TextView conversations;
        ImageButton favoriteButton;
        MaterialButton chatButton;
        ProgressBar loadingIndicator;

        PageViewHolder(@NonNull View itemView) {
            super(itemView);
            avatarImage = itemView.findViewById(R.id.full_avatar_image);
            avatarEmoji = itemView.findViewById(R.id.full_avatar_emoji);
            name = itemView.findViewById(R.id.full_name);
            description = itemView.findViewById(R.id.full_description);
            tags = itemView.findViewById(R.id.full_tags);
            conversations = itemView.findViewById(R.id.full_conversations);
            favoriteButton = itemView.findViewById(R.id.full_favorite_button);
            chatButton = itemView.findViewById(R.id.full_chat_button);
            loadingIndicator = itemView.findViewById(R.id.full_loading);
        }
    }
}
