<?php
declare(strict_types=1);

require_once __DIR__ . '/inc/data.php';

$role = $_GET['role'] ?? 'chairman';
$pageTitle = 'Стройка — демо';
$activeNav = '';
require __DIR__ . '/layout/header.php';
?>
    <div class="page-header">
        <div class="header-main">
            <div class="page-title">Демонстрация веб-интерфейса</div>
            <p class="page-subtitle">Выберите роль сверху и перейдите в разделы навигации. Данные из JSON, действия имитируются в браузере (localStorage).</p>
        </div>
    </div>
    <div class="kpi-grid" style="max-width:720px">
        <div class="kpi-card">
            <div class="kpi-value">1</div>
            <div class="kpi-label">Сводка и таблица — руководитель</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-value">2</div>
            <div class="kpi-label">Прораб: новая заявка и список</div>
        </div>
        <div class="kpi-card">
            <div class="kpi-value">3</div>
            <div class="kpi-label">ПДО и закупка: очереди</div>
        </div>
    </div>
    <p class="muted">Сброс демо-изменений: кнопка на странице карточки заявки или очистите localStorage ключ <code>stroika_demo_v1</code>.</p>
<?php
require __DIR__ . '/layout/footer.php';
