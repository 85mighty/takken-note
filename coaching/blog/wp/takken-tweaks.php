<?php
/*
 * Plugin Name: takken tweaks (NIPPONリアル)
 * Description: 宅建ノート用の調整。コメント欄をなくす・自分の記事どうしのピンバックを止める・トップの記事一覧を「サムネイル｜タイトル・説明」の行形式にする。
 *              ~/takken-note/coaching/blog/wp/ から deploy.sh が自動でコピーする（ここを直接編集しない）。
 */
if (!defined('ABSPATH')) exit;

// ---- コメント欄をなくす ----
add_filter('comments_open', '__return_false', 99);
add_filter('pings_open', '__return_false', 99);
add_filter('comments_array', '__return_empty_array', 99);
add_filter('get_comments_number', '__return_zero', 99);
add_filter('render_block', function ($html, $block) {            // ブロックテーマのコメント欄
    $n = $block['blockName'] ?? '';
    if (in_array($n, ['core/comments', 'core/post-comments', 'core/post-comments-form', 'core/comments-title', 'core/comment-template', 'core/post-comments-count', 'core/post-comments-link'], true)) return '';
    return $html;
}, 10, 2);
add_filter('comments_template', function () { return __DIR__ . '/takken-tweaks-empty.php'; }, 99);   // クラシックテーマのコメント欄

// ---- 自分のサイトへのリンクでピンバックを送らない ----
add_action('pre_ping', function (&$links) {
    $home = get_option('home');
    foreach ($links as $k => $l) if (strpos($l, $home) === 0) unset($links[$k]);
});

// ---- 記事一覧を行形式に（サムネイル左・タイトルと説明右。スマホでも横並び） ----
add_action('wp_head', function () {
    if (!(is_front_page() || is_home() || is_archive() || is_search())) return; ?>
<style id="takken-list">
.wp-block-post-template{display:block!important;grid-template-columns:none!important}
.wp-block-post-template>li{width:auto!important;max-width:none!important;margin:0 0 14px!important;padding:12px!important;background:#fff;border:1px solid #e3e6ee;border-radius:14px;box-shadow:0 1px 3px rgba(0,0,0,.05)}
.wp-block-post-template>li,.wp-block-post-template>li>.wp-block-group{display:grid!important;grid-template-columns:38% 1fr;grid-template-rows:auto auto 1fr;column-gap:16px;row-gap:4px;align-items:start}
.wp-block-post-template>li>.wp-block-group{grid-column:1/-1;padding:0!important;margin:0!important}
.wp-block-post-template .wp-block-post-featured-image{grid-column:1;grid-row:1/span 4;margin:0!important}
.wp-block-post-template .wp-block-post-featured-image img{width:100%;aspect-ratio:16/9;object-fit:cover;border-radius:10px}
.wp-block-post-template li>*:not(.wp-block-post-featured-image),.wp-block-post-template li>.wp-block-group>*:not(.wp-block-post-featured-image){grid-column:2;margin:0!important}
.wp-block-post-template .wp-block-post-title{font-size:1.05rem!important;line-height:1.45}
.wp-block-post-template .wp-block-post-excerpt{font-size:.88rem;color:#555;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.wp-block-post-template .wp-block-post-excerpt__more-text{display:none}
@media(max-width:600px){.wp-block-post-template>li,.wp-block-post-template>li>.wp-block-group{grid-template-columns:42% 1fr;column-gap:10px}
 .wp-block-post-template .wp-block-post-title{font-size:.95rem!important}}
</style>
<?php });
