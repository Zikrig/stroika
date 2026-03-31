<?php
declare(strict_types=1);

require_once __DIR__ . '/inc/data.php';

$role = $_GET['role'] ?? 'foreman';
$pageTitle = 'Мои заявки — демо';
$activeNav = 'foreman_list';

$requests = site_load_json('requests');
$users = site_load_json('users');
$jsonRequests = site_json_encode_for_js($requests);
$jsonUsers = site_json_encode_for_js($users);

require __DIR__ . '/layout/header.php';
?>
    <div class="page-header">
        <div class="header-main">
            <div class="page-title">Мои заявки (прораб id=10, демо)</div>
            <p class="page-subtitle">Фильтр: только заявки с <code>foreman_user_id === 10</code></p>
        </div>
        <a class="btn-primary" style="display:inline-block;text-decoration:none;padding:8px 16px" href="foreman_new.php?role=foreman">Новая заявка</a>
    </div>

    <div class="table-wrapper">
        <table>
            <thead>
            <tr>
                <th>Код</th>
                <th>Статус / этап</th>
                <th>Объект</th>
                <th>Наименование</th>
                <th>Срок</th>
            </tr>
            </thead>
            <tbody id="tbody"></tbody>
        </table>
    </div>
<?php
ob_start();
?>
<script>
(function () {
  var BASE = <?= $jsonRequests ?>;
  var USERS = <?= $jsonUsers ?>;
  var FOREMAN_ID = 10;

  function render() {
    var list = window.StroikaDemo.mergeRequests(BASE).filter(function (r) {
      return r.foreman_user_id === FOREMAN_ID;
    });
    var f = window.StroikaFmt;
    var role = new URLSearchParams(location.search).get('role') || 'foreman';
    document.getElementById('tbody').innerHTML = list
      .map(function (r) {
        return (
          '<tr><td class="col-id"><a class="link-code" href="request.php?code=' +
          encodeURIComponent(r.request_code) +
          '&role=' +
          encodeURIComponent(role) +
          '">' +
          f.escapeHtml(r.request_code) +
          '</a></td><td>' +
          f.formatStatus(r.status_code) +
          '<div>' +
          f.formatStage(r.stage_code) +
          '</div></td><td>' +
          f.escapeHtml(r.object_name || '') +
          '</td><td>' +
          f.escapeHtml(r.nomenclature_1c || r.name_from_foreman || '') +
          '</td><td>' +
          f.escapeHtml(r.need_by || '—') +
          '</td></tr>'
        );
      })
      .join('');
  }
  render();
})();
</script>
<?php
$extraScripts = ob_get_clean();
require __DIR__ . '/layout/footer.php';
