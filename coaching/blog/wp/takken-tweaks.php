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

// ---- 記事本文の部品（スタジオの blogify が出す tk-* クラス）。スマホでは表を行ごとのカードに畳む ----
add_action('wp_head', function () { if (!is_singular()) return; ?>
<style id="takken-content-tk">
.entry-content .tk-key{background:#fff3c4;border-left:6px solid #e0a800;padding:12px 16px;margin:18px 0;font-weight:700;line-height:1.7;border-radius:0 8px 8px 0}
.entry-content .tk-note{color:#6b7280;font-size:.9em;margin:8px 0 18px}
.entry-content .tk-big{text-align:center;font-size:2.4em;font-weight:900;color:#c0392b;margin:14px 0 6px;line-height:1.2}
.entry-content .tk-huge{font-size:1.25em;font-weight:700;line-height:2.1;margin:14px 0 18px;padding:10px 18px;background:#f7f9fc;border-radius:8px}
.entry-content .tk-huge b{text-decoration:underline wavy #3b82d6;text-decoration-thickness:2px;text-underline-offset:5px}
.entry-content .tk-rbox{display:inline-block;border:2px solid #b8312f;border-radius:6px;padding:0 10px;margin:2px 0}
.entry-content .tk-big small{display:block;font-size:.42em;color:#333;font-weight:700;margin-top:6px}
.entry-content ul.tk-steps,.entry-content ol.tk-steps{padding-left:1.4em;margin:10px 0 16px}
.entry-content .tk-steps li{margin:8px 0;line-height:1.8}
.entry-content .tk-two{display:grid;grid-template-columns:1fr 1fr;gap:16px;align-items:start}
.entry-content .tk-cover h2{font-size:1.5em;margin:0 0 8px}.entry-content .tk-cover h3{font-size:1.05em;font-weight:500;color:#444;margin:0 0 8px}
.entry-content .tk-tbl-wrap{margin:14px 0 18px}
.entry-content table.tk-tbl{width:100%;border-collapse:collapse;font-size:.95em;line-height:1.6}
.entry-content .tk-tbl th,.entry-content .tk-tbl td{border:1px solid #cfd6e4;padding:9px 12px;vertical-align:top;text-align:left}
.entry-content .tk-tbl thead th{background:#1a3d7c;color:#fff;font-weight:700}
.entry-content .tk-tbl tbody th{background:#f3f6fb;font-weight:700;white-space:nowrap}
.entry-content .tk-tbl td.c{text-align:center}
.entry-content .tk-tbl td.hi{background:#ffe8e4;font-weight:700}
.entry-content .tk-tbl td.lo{background:#e8f0ff}
.entry-content .tk-tbl tr.now td{background:#fff3c4;font-weight:700}
@media(max-width:640px){
  .entry-content .tk-two{grid-template-columns:1fr}
  .entry-content .tk-tbl thead{display:none}
  .entry-content .tk-tbl,.entry-content .tk-tbl tbody,.entry-content .tk-tbl tr{display:block;width:100%}
  .entry-content .tk-tbl tr{border:1px solid #cfd6e4;border-radius:10px;margin:0 0 10px;overflow:hidden;background:#fff}
  .entry-content .tk-tbl td,.entry-content .tk-tbl tbody th{display:flex;gap:10px;border:0;border-top:1px solid #e6eaf2;padding:8px 12px;text-align:left}
  .entry-content .tk-tbl tr>*:first-child{border-top:0;background:#f3f6fb;font-weight:700;display:block}
  .entry-content .tk-tbl td[data-label]:not(:first-child)::before{content:attr(data-label);flex:0 0 7em;color:#1a3d7c;font-weight:700}
  .entry-content .tk-tbl td[data-label=""]::before{display:none}
  .entry-content .tk-tbl td.c{text-align:left}
  .entry-content .tk-big{font-size:2em}
}
</style>
<?php });
