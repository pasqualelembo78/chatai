package com.intelligame.chatai;

import android.view.LayoutInflater;
import android.view.View;
import android.view.ViewGroup;
import android.widget.ImageButton;
import android.widget.TextView;

import androidx.annotation.NonNull;
import androidx.recyclerview.widget.RecyclerView;

import com.google.android.material.imageview.ShapeableImageView;

import java.util.HashSet;
import java.util.List;
import java.util.Set;

public class CharacterCardAdapter extends RecyclerView.Adapter<CharacterCardAdapter.ViewHolder> {

    private final List<HomeFragment.CharacterItem> characters;
    private final OnCharacterClickListener listener;
    private final OnFavoriteClickListener favoriteListener;
    private final Set<String> favoriteIds = new HashSet<>();
    private final boolean feedMode;

    public interface OnCharacterClickListener {
        void onCharacterClick(HomeFragment.CharacterItem character);
    }

    public interface OnFavoriteClickListener {
        void onFavoriteClick(HomeFragment.CharacterItem character, boolean isFavorite);
    }

    public CharacterCardAdapter(List<HomeFragment.CharacterItem> characters,
                                 OnCharacterClickListener listener,
                                 OnFavoriteClickListener favoriteListener) {
        this(characters, listener, favoriteListener, false);
    }

    public CharacterCardAdapter(List<HomeFragment.CharacterItem> characters,
                                 OnCharacterClickListener listener,
                                 OnFavoriteClickListener favoriteListener,
                                 boolean feedMode) {
        this.characters = characters;
        this.listener = listener;
        this.favoriteListener = favoriteListener;
        this.feedMode = feedMode;
    }

    public void setFavoriteIds(Set<String> ids) {
        favoriteIds.clear();
        if (ids != null) {
            favoriteIds.addAll(ids);
        }
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

    public boolean isFavorite(String characterId) {
        return favoriteIds.contains(characterId);
    }

    @NonNull
    @Override
    public ViewHolder onCreateViewHolder(@NonNull ViewGroup parent, int viewType) {
        int layoutRes = feedMode ? R.layout.item_character_feed : R.layout.item_character_card;
        View view = LayoutInflater.from(parent.getContext())
            .inflate(layoutRes, parent, false);
        return new ViewHolder(view);
    }

    @Override
    public void onBindViewHolder(@NonNull ViewHolder holder, int position) {
        HomeFragment.CharacterItem character = characters.get(position);

        AvatarLoader.loadAvatar(
            holder.itemView.getContext(),
            character.avatarImage,
            holder.avatarImage,
            holder.avatarEmoji,
            character.emoji
        );

        holder.name.setText(character.name);
        holder.description.setText(character.description);
        holder.tags.setText(character.getTagsString());
        holder.conversations.setText(character.getConversationsString() + " chat");

        if (character.intimacy > 0 && holder.intimacy != null) {
            holder.intimacy.setVisibility(View.VISIBLE);
            holder.intimacy.setText("\u2764 " + character.intimacy + "%");
        } else if (holder.intimacy != null) {
            holder.intimacy.setVisibility(View.GONE);
        }

        boolean isFav = favoriteIds.contains(character.id);
        holder.favoriteButton.setImageResource(
            isFav ? R.drawable.ic_favorite_filled : R.drawable.ic_favorite_border
        );
        holder.favoriteButton.setColorFilter(
            isFav ? 0xFFFF0000 : holder.itemView.getContext().getColor(R.color.on_surface_dim)
        );

        holder.card.setOnClickListener(v -> listener.onCharacterClick(character));

        if (holder.chatButton != null) {
            holder.chatButton.setOnClickListener(v -> listener.onCharacterClick(character));
        }

        holder.favoriteButton.setOnClickListener(v -> {
            boolean newState = !favoriteIds.contains(character.id);
            if (newState) {
                favoriteIds.add(character.id);
            } else {
                favoriteIds.remove(character.id);
            }
            notifyItemChanged(position);
            if (favoriteListener != null) {
                favoriteListener.onFavoriteClick(character, newState);
            }
        });
    }

    @Override
    public int getItemCount() {
        return characters.size();
    }

    static class ViewHolder extends RecyclerView.ViewHolder {
        final com.google.android.material.card.MaterialCardView card;
        final ShapeableImageView avatarImage;
        final TextView avatarEmoji;
        final TextView name;
        final TextView description;
        final TextView tags;
        final TextView conversations;
        final TextView intimacy;
        final ImageButton favoriteButton;
        final com.google.android.material.button.MaterialButton chatButton;

        ViewHolder(View itemView) {
            super(itemView);
            card = (com.google.android.material.card.MaterialCardView) itemView;
            avatarImage = itemView.findViewById(R.id.card_avatar_image);
            avatarEmoji = itemView.findViewById(R.id.card_avatar_emoji);
            name = itemView.findViewById(R.id.card_name);
            description = itemView.findViewById(R.id.card_description);
            tags = itemView.findViewById(R.id.card_tags);
            conversations = itemView.findViewById(R.id.card_conversations);
            intimacy = itemView.findViewById(R.id.card_intimacy);
            favoriteButton = itemView.findViewById(R.id.card_favorite_button);
            chatButton = itemView.findViewById(R.id.card_chat_button);
        }
    }
}
