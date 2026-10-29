<?php
/*
 * Plugin Name: takken tweaks (NIPPONリアル)
 * Description: 宅建ノート用の調整。コメント欄をなくす・自分の記事どうしのピンバックを止める。
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
// 記事一覧のデザインは takken-theme.php（ym-card）で行形式にしている
