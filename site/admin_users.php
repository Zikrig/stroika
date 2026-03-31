<?php
declare(strict_types=1);

require_once __DIR__ . '/inc/data.php';

$role = $_GET['role'] ?? 'admin';
$pageTitle = 'Пользователи — демо';
$activeNav = 'admin_users';

$users = site_load_json('users');
$jsonUsers = site_json_encode_for_js($users);

require __DIR__ . '/layout/header.php';
?>
    <div class="page-header">
        <div class="header-main">
            <div class="page-title">Пользователи и роли (демо)</div>
            <p class="page-subtitle">Данные из <code>site/data/users.json</code></p>
        </div>
    </div>

    <div class="filters" style="grid-template-columns: 1fr 1fr; max-width: 480px">
        <div class="filter-group">
            <label class="filter-label" for="roleFilter">Фильтр по роли</label>
            <select id="roleFilter" class="filter-select">
                <option value="">Все</option>
                <option value="foreman">Прораб</option>
                <option value="pdo">ПДО</option>
                <option value="procurement">Закупка</option>
                <option value="manager">Руководитель</option>
                <option value="viewer">Зритель</option>
                <option value="admin">Админ</option>
            </select>
        </div>
    </div>

    <div class="table-wrapper">
        <table>
            <thead>
            <tr>
                <th>ID</th>
                <th>Имя</th>
                <th>Username</th>
                <th>Роли</th>
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
  var USERS = <?= $jsonUsers ?>;

  function render() {
    var rf = document.getElementById('roleFilter').value;
    var rows = USERS.filter(function (u) {
      if (!rf) return true;
      return (u.roles || []).indexOf(rf) >= 0;
    });
    document.getElementById('tbody').innerHTML = rows
      .map(function (u) {
        return (
          '<tr><td>' +
          window.StroikaFmt.escapeHtml(String(u.id)) +
          '</td><td>' +
          window.StroikaFmt.escapeHtml(u.display_name || '') +
          '</td><td>' +
          window.StroikaFmt.escapeHtml(u.username || '') +
          '</td><td>' +
          window.StroikaFmt.escapeHtml((u.roles || []).join(', ')) +
          '</td></tr>'
        );
      })
      .join('');
  }
  document.getElementById('roleFilter').addEventListener('change', render);
  render();
})();
</script>
<?php
$extraScripts = ob_get_clean();
require __DIR__ . '/layout/footer.php';
