<?php
/**
 * Plugin Name: takken 테마 (seido-note와 동일 디자인 시스템, 2026-10-14)
 * Description: Twenty Twenty-Five(블록 테마) 위에 네이비+골드 스티키 헤더·푸터, 홈 히어로, 카드 목록,
 *   종이 배경, Noto Sans JP 볼드 위계, 모바일 가로 카드를 얹는다. 글 본문 컴포넌트(jp-policy-*) CSS 포함.
 *   카테고리 네비는 글이 있는 카테고리만 자동 노출.
 */
if (!defined('ABSPATH')) { exit; }

/* ---------- 카테고리 메타 ---------- */
function ym_cat_meta() {
    return array(
        'kakomon'     => array('📝', '年度別・分野別の過去問解説'),
        'kenri'       => array('⚖️', '民法・借地借家法・区分所有法'),
        'gyohou'      => array('🏢', '宅建業法のポイント整理'),
        'hourei'      => array('🗺️', '都市計画法・建築基準法など'),
        'zei-sonota'  => array('🧾', '税法・鑑定評価・免除科目'),
        'shiken-info' => array('📅', '試験日程・合格点・登録手続き'),
    );
}
function ym_cats() {
    $c = get_transient('ym_cats');
    if (is_array($c)) { return $c; }
    $terms = get_categories(array('hide_empty' => true, 'orderby' => 'count', 'order' => 'DESC'));
    $order = array_keys(ym_cat_meta());
    $out = array();
    foreach ($terms as $t) {
        if ($t->slug === 'uncategorized' || strpos($t->slug, '%') !== false || $t->name === '未分類') { continue; }
        $out[] = array('id' => $t->term_id, 'slug' => $t->slug, 'name' => $t->name, 'count' => (int) $t->count, 'url' => get_term_link($t));
    }
    usort($out, function ($a, $b) use ($order) {
        $ia = array_search($a['slug'], $order); $ib = array_search($b['slug'], $order);
        return ($ia === false ? 99 : $ia) <=> ($ib === false ? 99 : $ib);
    });
    set_transient('ym_cats', $out, 10 * MINUTE_IN_SECONDS);
    return $out;
}
add_action('save_post', function () { delete_transient('ym_cats'); });
add_action('created_category', function () { delete_transient('ym_cats'); });
add_action('edited_category', function () { delete_transient('ym_cats'); });

/* ---------- 목록 페이지 설정 ---------- */
add_filter('body_class', function ($c) {
    if (is_home() || is_archive() || is_search()) { $c[] = 'ym-listing'; }
    return $c;
});
add_action('pre_get_posts', function ($q) {
    if (!is_admin() && $q->is_main_query() && ($q->is_home() || $q->is_archive() || $q->is_search())) {
        $q->set('posts_per_page', 12);
    }
});

/* ---------- 웹폰트 ---------- */
add_action('wp_head', function () {
    echo '<link rel="preconnect" href="https://fonts.googleapis.com">' . "\n"
       . '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>' . "\n"
       . '<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700;900&display=swap" rel="stylesheet">' . "\n";
}, 1);

/* ---------- 헤더 ---------- */
add_action('wp_body_open', function () {
    $cats = ym_cats();
    $cur = is_category() ? get_queried_object() : null;
    ?>
<div class="ym-header"><div class="ym-header-in">
  <a class="ym-brand" href="<?php echo esc_url(home_url('/')); ?>">
    <span class="ym-brand-en">宅建<span>ノート</span></span>
    <span class="ym-brand-kr">宅建ノート｜行政手続き・申請ガイド</span>
  </a>
  <nav class="ym-nav" aria-label="메인">
    <a href="<?php echo esc_url(home_url('/')); ?>" class="<?php echo is_front_page() ? 'ym-on' : ''; ?>">ホーム</a>
    <?php foreach ($cats as $c) : ?>
    <a href="<?php echo esc_url($c['url']); ?>" class="<?php echo ($cur && $cur->term_id === $c['id']) ? 'ym-on' : ''; ?>"><?php echo esc_html($c['name']); ?></a>
    <?php endforeach; ?>
    <a href="<?php echo esc_url(home_url('/#ym-new')); ?>">新着</a>
  </nav>
</div></div>
    <?php
}, 5);

/* ---------- 카드 렌더 ---------- */
function ym_card($post) {
    $id = $post->ID;
    $cats = get_the_category($id);
    $cat = '';
    foreach ($cats as $c) { if ($c->slug !== 'uncategorized' && $c->name !== '未分類') { $cat = $c->name; break; } }
    $desc = get_post_meta($id, 'rank_math_description', true);
    if (!$desc) { $desc = wp_strip_all_tags(get_the_excerpt($post)); }
    $desc = mb_substr(trim(preg_replace('/\s+/u', ' ', wp_strip_all_tags($desc))), 0, 110);
    $thumb = get_the_post_thumbnail_url($id, 'medium_large');
    ob_start(); ?>
<article class="ym-card">
  <a class="ym-thumb" href="<?php echo esc_url(get_permalink($id)); ?>" tabindex="-1" aria-hidden="true">
    <?php if ($thumb) : ?><img src="<?php echo esc_url($thumb); ?>" alt="<?php echo esc_attr(get_the_title($id)); ?>" loading="lazy"><?php else : ?><span class="ym-noimg">宅建ノート</span><?php endif; ?>
  </a>
  <div class="ym-cbody">
    <?php if ($cat) : ?><span class="ym-cat"><?php echo esc_html($cat); ?></span><?php endif; ?>
    <h2 class="ym-ctitle"><a href="<?php echo esc_url(get_permalink($id)); ?>"><?php echo esc_html(get_the_title($id)); ?></a></h2>
    <time class="ym-date" datetime="<?php echo esc_attr(get_the_date('c', $id)); ?>"><?php echo esc_html(get_the_date('Y.m.d', $id)); ?></time>
    <p class="ym-cdesc"><?php echo esc_html($desc); ?></p>
  </div>
</article>
    <?php
    return ob_get_clean();
}

/* ---------- 홈 히어로 + 목록 ---------- */
add_action('wp_body_open', function () {
    if (!(is_home() || is_archive() || is_search())) { return; }
    global $wp_query;
    $cats = ym_cats();
    $meta = ym_cat_meta();
    $total = (int) wp_count_posts('post')->publish;

    if (is_front_page() && !is_paged()) {
        $latest = get_posts(array('numberposts' => 3, 'post_status' => 'publish'));
        ?>
<section class="ym-hero"><div class="ym-hero-in">
  <p class="ym-eyebrow">宅建ノート · 行政手続き・申請ガイド</p>
  <h1 class="ym-h1">過去問は、解きっぱなしにしない。</h1>
  <p class="ym-sub">年度別の過去問解説、分野別の要点整理、解説PDFのダウンロードまで。宅建士試験の独学を支える復習ノートです。</p>
  <?php if ($cats) : ?>
  <div class="ym-chips">
    <?php foreach ($cats as $c) : $m = isset($meta[$c['slug']]) ? $meta[$c['slug']][0] : '📌'; ?>
    <a href="<?php echo esc_url($c['url']); ?>"><?php echo esc_html($m . ' ' . $c['name']); ?> <small><?php echo (int) $c['count']; ?></small></a>
    <?php endforeach; ?>
  </div>
  <?php endif; ?>
  <?php if ($latest) : ?>
  <div class="ym-latest">
    <p class="ym-latest-head">🆕 新着の解説</p>
    <ul>
      <?php foreach ($latest as $p) : ?>
      <li><a href="<?php echo esc_url(get_permalink($p)); ?>"><?php echo esc_html(get_the_title($p)); ?></a> <time><?php echo esc_html(get_the_date('m.d', $p)); ?></time></li>
      <?php endforeach; ?>
    </ul>
  </div>
  <?php endif; ?>
  <p class="ym-stats">全<strong><?php echo esc_html($total); ?></strong>件のガイド 手続き・申請ガイド</p>
</div></section>
        <?php
    }
    ?>
<main class="ym-main"><div class="ym-wrap">
  <?php if (is_front_page() && !is_paged() && $cats) : ?>
  <h2 class="ym-sec">カテゴリから探す</h2>
  <div class="ym-catgrid">
    <?php foreach ($cats as $c) : $m = isset($meta[$c['slug']]) ? $meta[$c['slug']] : array('📌', ''); ?>
    <a class="ym-catcard" href="<?php echo esc_url($c['url']); ?>">
      <span class="ym-ci"><?php echo esc_html($m[0]); ?></span>
      <b><?php echo esc_html($c['name']); ?></b>
      <span class="ym-cd"><?php echo esc_html($m[1]); ?></span>
      <em><?php echo (int) $c['count']; ?>件</em>
    </a>
    <?php endforeach; ?>
  </div>
  <?php endif; ?>

  <?php if (is_archive()) : ?>
  <header class="ym-archead">
    <h1 class="ym-h1a"><?php echo esc_html((is_category() || is_tag()) ? single_term_title('', false) : wp_strip_all_tags(get_the_archive_title())); ?></h1>
    <?php $d = term_description(); if ($d) { echo '<div class="ym-archdesc">' . wp_kses_post($d) . '</div>'; } ?>
  </header>
  <?php elseif (is_search()) : ?>
  <header class="ym-archead"><h1 class="ym-h1a">“<?php echo esc_html(get_search_query()); ?>” 検索結果</h1></header>
  <?php else : ?>
  <h2 class="ym-sec" id="ym-new">新着</h2>
  <?php endif; ?>

  <?php if (have_posts()) : ?>
  <div class="ym-grid">
    <?php while (have_posts()) { the_post(); echo ym_card(get_post()); } wp_reset_postdata(); ?>
  </div>
  <?php
    $links = paginate_links(array('total' => (int) $wp_query->max_num_pages, 'current' => max(1, (int) get_query_var('paged')),
        'mid_size' => 1, 'prev_text' => '←', 'next_text' => '→', 'type' => 'plain'));
    if ($links) { echo '<nav class="ym-pager" aria-label="ページ">' . $links . '</nav>'; }
  ?>
  <?php else : ?>
  <p class="ym-empty">まだ記事がありません.</p>
  <?php endif; ?>
</div></main>
    <?php
}, 20);

/* ---------- 푸터 ---------- */
add_action('wp_footer', function () {
    ?>
<footer class="ym-footer"><div class="ym-footer-in">
  <span class="ym-foot-brand">宅建<b>ノート</b></span>
  <nav class="ym-foot-links" aria-label="サイト情報">
    <a href="<?php echo esc_url(home_url('/about/')); ?>">運営者情報</a>
    <a href="<?php echo esc_url(home_url('/contact/')); ?>">お問い合わせ</a>
    <a href="<?php echo esc_url(home_url('/privacy-policy/')); ?>">プライバシーポリシー</a>
    <a href="<?php echo esc_url(home_url('/terms/')); ?>">利用規約</a>
    <a href="<?php echo esc_url(home_url('/disclaimer/')); ?>">免責事項</a>
    <a href="<?php echo esc_url(home_url('/editorial-policy/')); ?>">運営方針</a>
  </nav>
  <span class="ym-foot-line">© <?php echo esc_html(date_i18n('Y')); ?> 宅建ノート — 宅建士試験の過去問解説・分野別まとめ・資料ダウンロード</span>
</div></footer>
    <?php
}, 5);

/* ---------- 스타일 ---------- */
add_action('wp_head', function () {
    ?>
<style>
:root{--ym-navy:#0e1730;--ym-gold:#e8c56a;--ym-blue:#1e3a8a}
html{scroll-behavior:smooth}
body{font-family:'Noto Sans JP',-apple-system,system-ui,'Apple SD Gothic Neo','Malgun Gothic',sans-serif !important;
  background:#f3efe6 url('/wp-content/uploads/ym-bg/paper-w.jpg') repeat top center !important;color:#1f2328;-webkit-font-smoothing:antialiased}
button,input,select,textarea{font-family:inherit}
/* 블록 테마 기본 헤더·푸터 숨김(DOM 유지) */
header.wp-block-template-part, footer.wp-block-template-part{display:none !important}
.wp-site-blocks{padding:0 !important}
body{display:flex;flex-direction:column;min-height:100vh}
.wp-site-blocks,.ym-main{flex:1 0 auto}
.wp-site-blocks > *{margin-block-start:0 !important}
body.ym-listing main#wp--skip-link--target, body.ym-listing .wp-site-blocks > main{display:none !important}

/* 헤더 */
.ym-header{position:sticky;top:0;z-index:999;background:var(--ym-navy);border-bottom:1px solid rgba(255,255,255,.08);box-shadow:0 2px 14px rgba(10,16,35,.35)}
body.admin-bar .ym-header{top:32px}
.ym-header-in{max-width:1160px;margin:0 auto;padding:12px 18px;display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap}
.ym-brand{text-decoration:none !important;display:block;line-height:1.25}
.ym-brand-en{display:block;font-size:21px;font-weight:900;letter-spacing:.18em;color:#fff}
.ym-brand-en span{color:var(--ym-gold)}
.ym-brand-kr{display:block;font-size:11px;color:#93a1c4;letter-spacing:.03em;margin-top:1px}
.ym-nav{display:flex;align-items:center;gap:4px;flex-wrap:wrap}
.ym-nav a{color:rgba(255,255,255,.82);text-decoration:none;font-size:13.5px;font-weight:700;padding:7px 12px;border-radius:999px;transition:background .15s,color .15s;white-space:nowrap}
.ym-nav a:hover{color:#fff;background:rgba(255,255,255,.10)}
.ym-nav a.ym-on{color:var(--ym-navy);background:var(--ym-gold)}

/* 히어로 */
.ym-hero{background:linear-gradient(rgba(14,23,48,.78),rgba(14,23,48,.9)),url('/wp-content/uploads/ym-bg/hero-w.jpg') center/cover no-repeat;padding:34px 16px 24px;color:#fff}
.ym-hero-in{max-width:1000px;margin:0 auto;text-align:center}
.ym-eyebrow{font-size:12px;letter-spacing:.2em;color:var(--ym-gold);font-weight:700;margin:0 0 8px}
.ym-h1{font-size:clamp(24px,4.2vw,36px) !important;font-weight:900 !important;line-height:1.35;margin:0 0 8px !important;color:#fff !important}
.ym-sub{font-size:14.5px;line-height:1.7;color:#cdd6ee;margin:0 auto 16px;max-width:640px}
.ym-chips{display:flex;flex-wrap:wrap;justify-content:center;gap:8px;margin-bottom:18px}
.ym-chips a{background:rgba(255,255,255,.1);border:1px solid rgba(255,255,255,.22);color:#fff;text-decoration:none;font-size:13px;font-weight:700;padding:7px 14px;border-radius:999px}
.ym-chips a small{color:var(--ym-gold);font-weight:700;margin-left:3px}
.ym-chips a:hover{background:var(--ym-gold);color:var(--ym-navy)}
.ym-chips a:hover small{color:var(--ym-navy)}
.ym-latest{box-sizing:border-box;width:100%;max-width:820px;margin:0 auto;background:rgba(255,255,255,.97);border-radius:14px;padding:14px 20px 10px;text-align:left;box-shadow:0 10px 30px rgba(0,0,0,.25)}
.ym-latest-head{font-weight:900;font-size:15px;color:var(--ym-blue);margin:0 0 4px}
.ym-latest ul{list-style:none;margin:0;padding:0}
.ym-latest li{display:flex;justify-content:space-between;gap:12px;padding:8px 0;border-top:1px dashed #e3e8f2;font-size:14px;line-height:1.55}
.ym-latest li:first-child{border-top:0}
.ym-latest li a{color:#1f2937;text-decoration:none;font-weight:500}
.ym-latest li a:hover{color:var(--ym-blue);text-decoration:underline}
.ym-latest time{color:#9aa3b2;font-size:12px;white-space:nowrap}
.ym-stats{font-size:12px;color:#93a1c4;margin:14px 0 0}
.ym-stats strong{color:#fff}

/* 본문 래퍼 */
.ym-main{padding:6px 0 10px}
.ym-wrap{width:min(1160px,94vw);margin:0 auto;padding-top:6px}
.ym-sec{font-size:19px !important;font-weight:900 !important;margin:26px 0 14px !important;padding-left:12px;border-left:4px solid var(--ym-blue);letter-spacing:.01em}
.ym-archead{margin:26px 0 16px;background:#fff;border-radius:12px;padding:20px 24px;border:1px solid #e5e7eb}
.ym-h1a{font-size:24px !important;font-weight:900 !important;margin:0 !important}
.ym-archdesc{color:#5b6570;margin-top:6px;font-size:14px}
.ym-empty{background:#fff;border-radius:12px;padding:30px;text-align:center;color:#6b7280}

/* 카테고리 카드 */
.ym-catgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}
.ym-catcard{background:#fff;border:1px solid #e5e7eb;border-radius:14px;padding:16px;text-decoration:none;color:#111827;display:flex;flex-direction:column;gap:3px;transition:transform .15s,box-shadow .15s}
.ym-catcard:hover{transform:translateY(-3px);box-shadow:0 8px 20px rgba(17,24,39,.10)}
.ym-ci{font-size:22px}
.ym-catcard b{font-size:16px;font-weight:900}
.ym-cd{font-size:12.5px;color:#6b7280}
.ym-catcard em{font-style:normal;font-size:12px;color:var(--ym-blue);font-weight:700;margin-top:4px}

/* 카드 그리드 */
.ym-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:22px;align-items:start}
.ym-card{background:#fff;border:1px solid #e6e8eb;border-radius:12px;overflow:hidden;transition:transform .15s,box-shadow .15s}
.ym-card:hover{transform:translateY(-4px);box-shadow:0 8px 22px rgba(16,28,51,.1)}
.ym-thumb{display:block;line-height:0;background:var(--ym-navy)}
.ym-thumb img{width:100%;aspect-ratio:1/1;object-fit:cover;display:block}
.ym-noimg{display:flex;align-items:center;justify-content:center;aspect-ratio:1/1;color:var(--ym-gold);font-weight:900;letter-spacing:.16em;font-size:15px}
.ym-cbody{padding:14px 16px 18px}
.ym-cat{display:inline-block;background:#d94f46;color:#fff;font-size:11.5px;font-weight:700;padding:3px 10px;border-radius:999px}
.ym-ctitle{font-size:16.5px !important;font-weight:700 !important;line-height:1.5 !important;margin:8px 0 0 !important}
.ym-ctitle a{color:#1a5f9e;text-decoration:none}
.ym-ctitle a:hover{text-decoration:underline}
.ym-date{display:block;font-size:12px;color:#8a929b;margin-top:4px}
.ym-cdesc{font-size:13.5px;line-height:1.7;color:#5b6570;margin:8px 0 0;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}

/* 페이지네이션 */
.ym-pager{display:flex;justify-content:center;align-items:center;gap:7px;flex-wrap:wrap;margin:28px 0 8px;background:#fff;border-radius:12px;padding:16px}
.ym-pager .page-numbers{display:inline-block;min-width:40px;text-align:center;padding:9px 13px;border-radius:999px;background:#fff;border:1.5px solid #dfe4ef;color:#1f2937;font-weight:700;font-size:14px;text-decoration:none}
.ym-pager a.page-numbers:hover{border-color:var(--ym-navy);color:var(--ym-navy)}
.ym-pager .page-numbers.current{background:var(--ym-navy);color:var(--ym-gold);border-color:var(--ym-navy)}
.ym-pager .page-numbers.dots{border:0;background:transparent;min-width:auto;padding:9px 2px;color:#9aa3b2}

/* 푸터 */
.ym-footer{background:var(--ym-navy);margin-top:34px}
.ym-footer-in{max-width:1160px;margin:0 auto;text-align:center;padding:26px 16px 28px}
.ym-foot-brand{display:block;font-size:16px;font-weight:900;letter-spacing:.18em;color:#fff;margin-bottom:5px}
.ym-foot-brand b{color:var(--ym-gold)}
.ym-foot-line{display:block;font-size:12px;color:#93a1c4;letter-spacing:.02em}
.ym-foot-links{display:flex;flex-wrap:wrap;justify-content:center;gap:4px 18px;margin:2px 0 12px}
.ym-foot-links a{color:#cdd6ee;font-size:12.5px;font-weight:500;text-decoration:none}
.ym-foot-links a:hover{color:var(--ym-gold);text-decoration:underline}

/* 제목 볼드 위계 */
h1,h2,h3,h4,h5{font-weight:700}
.wp-block-post-title{font-weight:900 !important;line-height:1.45 !important}

/* ===== 글 페이지 ===== */
body:is(.single,.page){--wp--style--global--content-size:860px}
body:is(.single,.page) .wp-block-post-featured-image{display:none}
body:is(.single,.page) .wp-site-blocks > main{background:#fff;width:min(920px,94vw);max-width:920px;margin:24px auto 0 !important;border-radius:14px;padding:28px 34px 20px !important;box-shadow:0 2px 14px rgba(16,28,51,.06)}
body:is(.single,.page) .wp-site-blocks > main .alignfull,body:is(.single,.page) .wp-site-blocks > main .alignwide{max-width:100%}
body:is(.single,.page) .entry-content{font-size:16px;line-height:1.95}
body:is(.single,.page) .wp-block-post-title{font-size:clamp(24px,4vw,32px) !important}
body:is(.single,.page) .wp-site-blocks > main > .wp-block-group{padding-top:0 !important;padding-bottom:12px !important}
body:is(.single,.page) .wp-site-blocks > main{margin-top:24px !important}
body:is(.single,.page) .wp-site-blocks > main > .wp-block-group, body:is(.single,.page) .wp-site-blocks > main .entry-content{margin-left:0 !important;margin-right:0 !important;padding-left:0 !important;padding-right:0 !important;max-width:100% !important;width:auto !important}
body:is(.single,.page) .entry-content > *{max-width:100%}
body:is(.single,.page) .wp-block-post-title{margin:0 0 12px !important}
/* 메타: 著者・'カテゴリ:' 라벨 숨기고 카테고리 칩만 */
body:is(.single,.page) .wp-block-group.has-small-font-size > p.wp-block-paragraph, body:is(.single,.page) .wp-block-post-author-name{display:none !important}
body:is(.single,.page) .wp-block-group.has-small-font-size{margin-bottom:18px !important}
.taxonomy-category a{background:#d94f46;color:#fff !important;font-size:12px;font-weight:700;padding:3px 11px;border-radius:999px;text-decoration:none}

/* ===== 본문 컴포넌트 (seido-note 이식) ===== */
<?php echo file_get_contents(__DIR__ . '/takken-content.css'); ?>

/* ===== 모바일 ===== */
@media(max-width:900px){.ym-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.ym-catgrid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:640px){
  body{overflow-x:hidden}
  .ym-header-in{padding:10px 12px;gap:8px}
  .ym-brand-en{font-size:17px}
  .ym-brand-kr{display:none}
  .ym-nav{width:100%;overflow-x:auto;flex-wrap:nowrap;-webkit-overflow-scrolling:touch;scrollbar-width:none}
  .ym-nav::-webkit-scrollbar{display:none}
  .ym-nav a{font-size:12.5px;padding:6px 10px}
  .ym-hero{padding:20px 12px 16px}
  .ym-sub{font-size:13px;margin-bottom:12px}
  .ym-latest{padding:12px 14px 8px}
  .ym-latest li{font-size:13px}
  .ym-wrap{width:auto;margin:0 10px}
  .ym-sec{font-size:17px !important;margin:20px 0 11px !important}
  .ym-catgrid{grid-template-columns:1fr 1fr;gap:10px}
  .ym-catcard{padding:13px}
  .ym-grid{display:block}
  .ym-card{display:grid;grid-template-columns:104px minmax(0,1fr);column-gap:12px;align-items:start;padding:10px;margin-bottom:10px;border-radius:12px}
  .ym-card:hover{transform:none}
  .ym-thumb{grid-row:1/span 1;border-radius:9px;overflow:hidden}
  .ym-thumb img,.ym-noimg{width:104px !important;height:104px !important;aspect-ratio:1/1;font-size:11px}
  .ym-cbody{padding:0}
  .ym-ctitle{font-size:14px !important;line-height:1.45 !important;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;margin-top:4px !important}
  .ym-cat{font-size:10.5px;padding:2px 8px}
  .ym-date{font-size:11px;margin-top:3px}
  .ym-cdesc{font-size:12px;line-height:1.55;-webkit-line-clamp:2;margin-top:4px}
  .ym-archead{padding:16px 16px;margin:18px 0 12px}
  .ym-h1a{font-size:20px !important}
  body:is(.single,.page) .wp-site-blocks > main{width:auto;margin:10px 8px 0 !important;padding:18px 14px 12px !important}
  .ym-footer{margin-top:22px}
  .ym-footer-in{padding:20px 12px 24px}
  .ym-foot-line{font-size:11px}
  .ym-foot-links{gap:4px 14px}
  .ym-foot-links a{font-size:12px}
}
</style>
    <?php
}, 99);
