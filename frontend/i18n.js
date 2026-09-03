                                                               
(() => {
  'use strict';

  const DEFAULT_LOCALE = 'en';
  const STORAGE_KEY = 'instagram-osint-locale-v1';
  const SUPPORTED = new Set(['en', 'tr', 'zh-CN', 'ru']);
  const HTML_LANG = {en:'en', tr:'tr', 'zh-CN':'zh-Hans', ru:'ru'};
  const FORMAT_LOCALE = {en:'en-US', tr:'tr-TR', 'zh-CN':'zh-CN', ru:'ru-RU'};
  const entries = [
                        
    ['app.title','Instagram OSINT','Instagram OSINT','Instagram OSINT','Instagram OSINT'],
    ['language.label','Language','Dil','语言','Язык'],
    ['actions.settings','Analysis settings','Analiz ayarları','分析设置','Настройки анализа'],
    ['actions.recalculate','Recalculate','Analizi yenile','重新分析','Пересчитать'],
    ['actions.refresh','Refresh','Yenile','刷新','Обновить'],
    ['actions.search','Search','Sorgula','查询','Найти'],
    ['actions.done','Done','Tamam','完成','Готово'],
    ['actions.all','All','Tümü','全部','Все'],
    ['actions.none','None','Hiçbiri','无','Ничего'],
    ['actions.fast','Fast','Hızlı','快速','Быстро'],
    ['actions.stop','Stop analysis','Analizi durdur','停止分析','Остановить анализ'],
    ['actions.openReport','Open report','Raporu aç','打开报告','Открыть отчёт'],
    ['actions.viewAll','View all people','Tüm kişileri göster','查看全部人员','Показать всех'],
    ['actions.open','Open','Aç','打开','Открыть'],
    ['actions.openLink','Open link','Bağlantıyı aç','打开链接','Открыть ссылку'],
    ['search.placeholder','Instagram username','Instagram kullanıcı adı','Instagram 用户名','Имя пользователя Instagram'],
    ['search.target','Target','Hedef','目标','Цель'],

                                       
    ['phase.title','Analysis sections (default: fast)','Analiz bölümleri (varsayılan: hızlı)','分析模块（默认：快速）','Разделы анализа (по умолчанию: быстро)'],
    ['phase.depth','Network scan depth','Ağ tarama derinliği','网络扫描深度','Глубина сканирования сети'],
    ['phase.repetitions','repetitions','tekrar','次重复','повторов'],
    ['phase.depthHelp','Repeats discovery and chaining. Higher values can find more candidates and strengthen repeated signals.','Keşif ve zincir taramasını tekrarlar. Yüksek değer daha fazla aday bulabilir ve tekrar sinyalini güçlendirebilir.','重复执行发现和链式扫描。数值越高，可能找到更多候选并增强重复信号。','Повторяет поиск и цепочное сканирование. Большее значение может найти больше кандидатов и усилить повторяющиеся сигналы.'],
    ['phase.rateWarning','Values 6–15 take longer and may trigger Instagram rate limits.','6–15 daha uzun sürer ve Instagram istek sınırını tetikleyebilir.','6–15 会耗时更长，并可能触发 Instagram 频率限制。','Значения 6–15 работают дольше и могут вызвать ограничение запросов Instagram.'],
    ['phase.excludeWeak','Exclude weak algorithmic suggestions','Zayıf algoritmik önerileri çıkar','排除弱算法推荐','Исключить слабые алгоритмические рекомендации'],
    ['phase.presence','26 — profile access','26 — profil erişimi','26 — 资料访问','26 — доступ к профилю'],
    ['phase.dsa','27 — account transparency','27 — hesap şeffaflığı','27 — 账户透明度','27 — прозрачность аккаунта'],
    ['phase.inflate','28 — profile field scan','28 — profil alanı taraması','28 — 资料字段扫描','28 — сканирование полей профиля'],
    ['phase.archeology','29 — past activity','29 — geçmiş etkinlik','29 — 历史活动','29 — прошлая активность'],
    ['phase.tagged','30 — tagged content','30 — etiketli içerik','30 — 被标记内容','30 — отмеченный контент'],
    ['phase.news','31 — inbox signals','31 — mesaj kutusu sinyalleri','31 — 收件箱信号','31 — сигналы входящих'],
    ['phase.chain','32 — connection discovery','32 — bağlantı keşfi','32 — 关联发现','32 — поиск связей'],
    ['phase.internal','33 — target details','33 — hedef ayrıntıları','33 — 目标详情','33 — сведения о цели'],
    ['phase.followgraph','34 — follow network','34 — takip ağı','34 — 关注网络','34 — сеть подписок'],
    ['phase.reciprocal','35 — recommendation overlap','35 — öneri örtüşmesi','35 — 推荐重合','35 — пересечение рекомендаций'],
    ['phase.banyan','37 — share ranking','37 — paylaşım sırası','37 — 分享排序','37 — рейтинг отправки'],
    ['phase.often404','legacy / often unavailable','eski / sık erişilemiyor','旧接口 / 经常不可用','старый метод / часто недоступен'],
    ['phase.approx2m','about 2 min','yaklaşık 2 dk','约 2 分钟','около 2 мин'],
    ['phase.approx2to5m','about 2–5 min','yaklaşık 2–5 dk','约 2–5 分钟','около 2–5 мин'],
    ['phase.approx1m','about 1 min','yaklaşık 1 dk','约 1 分钟','около 1 мин'],
    ['phase.approx30s','about 30 sec','yaklaşık 30 sn','约 30 秒','около 30 сек'],
    ['phase.approx10s','about 10 sec','yaklaşık 10 sn','约 10 秒','около 10 сек'],
    ['log.live','LIVE ANALYSIS','CANLI ANALİZ','实时分析','АНАЛИЗ В РЕАЛЬНОМ ВРЕМЕНИ'],
    ['log.progress','Analysis progress','Analiz ilerlemesi','分析进度','Ход анализа'],
    ['log.preparing','Preparing','Hazırlanıyor','准备中','Подготовка'],
    ['log.preparingSteps','Preparing analysis steps.','Analiz adımları hazırlanıyor.','正在准备分析步骤。','Подготавливаются этапы анализа.'],
    ['log.rawShow','Show technical details','Teknik ayrıntıları göster','显示技术详情','Показать технические детали'],
    ['log.rawReport','Show raw technical report','Teknik metin raporunu göster','显示原始技术报告','Показать исходный технический отчёт'],
    ['log.advanced','Advanced view','Gelişmiş görünüm','高级视图','Расширенный вид'],
    ['log.groupedByProbability','People were grouped by model confidence.','Kişiler model güvenine göre gruplandı.','人员已按模型置信度分组。','Люди сгруппированы по уверенности модели.'],
    ['log.analysisFor','Analysis for {username}','{username} analizi','{username} 的分析','Анализ для {username}'],
    ['log.runMeta','{mode} · {sections} sections · Network depth {depth}','{mode} · {sections} bölüm · Ağ derinliği {depth}','{mode} · {sections} 个模块 · 网络深度 {depth}','{mode} · разделов: {sections} · глубина сети: {depth}'],

                                        
    ['stats.verified','Very high confidence','Çok yüksek model güveni','模型置信度极高','Очень высокая уверенность модели'],
    ['stats.high','High confidence','Yüksek model güveni','高模型置信度','Высокая уверенность модели'],
    ['stats.medium','Medium confidence','Orta model güveni','中等模型置信度','Средняя уверенность модели'],
    ['stats.low','Low confidence','Düşük model güveni','低模型置信度','Низкая уверенность модели'],
    ['stats.noise','Insufficient / unknown','Yetersiz / bilinmiyor','信号不足 / 未知','Недостаточно / неизвестно'],
    ['stats.total','Total','Toplam','总计','Всего'],
    ['stats.veryHigh','Very high confidence','Çok yüksek güven','极高置信度','Очень высокая уверенность'],
    ['stats.highShort','High confidence','Yüksek güven','高置信度','Высокая уверенность'],
    ['stats.mediumShort','Medium confidence','Orta güven','中等置信度','Средняя уверенность'],
    ['stats.lowShort','Low confidence','Düşük güven','低置信度','Низкая уверенность'],
    ['stats.weak','Insufficient / unknown','Yetersiz / bilinmiyor','不足 / 未知','Недостаточно / неизвестно'],
    ['stats.thresholdVeryHigh','Score ≥ 99','Skor ≥ 99','分数 ≥ 99','Оценка ≥ 99'],
    ['stats.thresholdHigh','Score ≥ 80','Skor ≥ 80','分数 ≥ 80','Оценка ≥ 80'],
    ['stats.thresholdMedium','Score ≥ 40','Skor ≥ 40','分数 ≥ 40','Оценка ≥ 40'],
    ['stats.thresholdLow','Score ≥ 15','Skor ≥ 15','分数 ≥ 15','Оценка ≥ 15'],
    ['stats.thresholdInsufficient','Score < 15 or none','Skor < 15 veya yok','分数 < 15 或无分数','Оценка < 15 или отсутствует'],
    ['stats.scoreCoverage','{scored} scored · {unscored} unscored','{scored} skorlu · {unscored} skorsuz','{scored} 个已评分 · {unscored} 个未评分','С оценкой: {scored} · без оценки: {unscored}'],
    ['panel.target','TARGET','HEDEF','目标','ЦЕЛЬ'],
    ['panel.summary','SUMMARY','ÖZET','摘要','СВОДКА'],
    ['panel.report','REPORT','RAPOR','报告','ОТЧЁТ'],
    ['panel.relationship','Relationship analysis','Bağlantı analizi','关联分析','Анализ связей'],
    ['panel.people','PEOPLE','KİŞİLER','人员','ЛЮДИ'],
    ['graph.legend','Model confidence categories','Model güveni kategorileri','模型置信度类别','Категории уверенности модели'],
    ['graph.metrics','METRICS','ÖLÇÜMLER','指标','МЕТРИКИ'],
    ['graph.visibleNodes','visible nodes','görünen düğüm','可见节点','видимых узлов'],
    ['graph.totalPeople','total people','toplam kişi','总人数','всего людей'],
    ['graph.minimumScore','minimum score','en düşük skor','最低分数','минимальный балл'],
    ['graph.zoomOut','Zoom out','Uzaklaştır','缩小','Уменьшить'],
    ['graph.zoomIn','Zoom in','Yakınlaştır','放大','Увеличить'],
    ['graph.fit','Fit graph','Grafiği sığdır','适配图表','Вписать граф'],
    ['graph.reset','Reset graph view','Grafik görünümünü sıfırla','重置图表视图','Сбросить вид графа'],
    ['graph.instructions','{count} people · stronger signals are closer to the center · select, open details, drag or zoom','{count} kişi · güçlü sinyaller merkeze daha yakın · seç, ayrıntıyı aç, sürükle veya yakınlaştır','{count} 人 · 信号越强越靠近中心 · 可选择、打开详情、拖动或缩放','{count} чел. · сильные сигналы ближе к центру · выберите, откройте сведения, перетащите или измените масштаб'],
    ['graph.aria','Instagram relationship graph arranged by signal strength','Sinyal gücüne göre düzenlenmiş Instagram ilişki grafiği','按信号强度排列的 Instagram 关联图','Граф связей Instagram, упорядоченный по силе сигналов'],
    ['graph.targetAria','Target {username}','Hedef {username}','目标 {username}','Цель {username}'],
    ['graph.personAria','{username}, {score}','{username}, {score}','{username}，{score}','{username}, {score}'],
    ['graph.targetTitle','Target: {username} (pk={pk})','Hedef: {username} (pk={pk})','目标：{username}（pk={pk}）','Цель: {username} (pk={pk})'],
    ['filter.search','Search username or name…','Kullanıcı veya ad ara…','搜索用户名或姓名…','Поиск по имени или логину…'],
    ['filter.atLeast','At least','En az','至少','Не менее'],
    ['filter.probability','Model confidence','Model güveni','模型置信度','Уверенность модели'],
    ['filter.profile','Profile','Profil','资料','Профиль'],
    ['filter.private','Private','Gizli','私密','Закрытый'],
    ['filter.blueTick','Verified account','Mavi tikli','认证账户','Подтверждённый'],
    ['table.rank','#','#','#','#'],
    ['table.user','User','Kullanıcı','用户','Пользователь'],
    ['table.signal','Signal','Sinyal','信号','Сигнал'],
    ['table.evidence','Evidence','Kanıtlar','依据','Основания'],
    ['table.probability','Model score ▾','Model skoru ▾','模型分数 ▾','Оценка модели ▾'],
    ['nav.people','People','Kişiler','人员','Люди'],
    ['nav.network','Network graph','Ağ grafiği','网络图','Граф связей'],
    ['nav.target','Target','Hedef','目标','Цель'],
    ['nav.signals','Signals','Sinyaller','信号','Сигналы'],
    ['nav.report','Report','Rapor','报告','Отчёт'],
    ['signals.noCapture','No saved suggestion data was found for this analysis.','Bu analiz için kayıtlı öneri verisi bulunamadı.','本次分析未找到已保存的推荐数据。','Для этого анализа не найдено сохранённых данных рекомендаций.'],
    ['signals.coverage','Coverage {coverage} / target {target}','Kapsama {coverage} / hedef {target}','覆盖率 {coverage} / 目标 {target}','Охват {coverage} / цель {target}'],
    ['signals.coverageUnknown','Coverage cannot be calculated because the target follower count is unavailable.','Hedefin takipçi sayısı alınamadığı için kapsama hesaplanamıyor.','由于无法获取目标粉丝数，因此无法计算覆盖率。','Охват нельзя рассчитать: число подписчиков цели недоступно.'],
    ['signals.captureCount','{count} captures','{count} yakalama','{count} 次采集','Снимков: {count}'],
    ['signals.pool','Pool: {count} people','Havuz: {count} kişi','候选池：{count} 人','Пул: {count} чел.'],
    ['signals.captures','Captures: {count}','Yakalama: {count}','采集次数：{count}','Снимки: {count}'],
    ['signals.captureFiles','Capture files ({count})','Yakalama dosyaları ({count})','采集文件（{count}）','Файлы снимков ({count})'],
    ['signals.surfacesSeen','Sources seen','Görülen kaynaklar','出现过的来源','Обнаруженные источники'],
    ['signals.bestieTitle','Found in Close Friends suggestions','Yakın Arkadaşlar önerilerinde bulundu','出现在密友推荐中','Найдено в рекомендациях близких друзей'],
    ['signals.username','Username','Kullanıcı adı','用户名','Имя пользователя'],
    ['signals.fullName','Full name','Tam ad','姓名','Полное имя'],
    ['signals.flags','Flags','İşaretler','标记','Признаки'],
    ['signals.score','Score','Skor','分数','Оценка'],
    ['signals.coefficientTitle','Instagram coefficient (0–100)','Instagram katsayısı (0–100)','Instagram 系数（0–100）','Коэффициент Instagram (0–100)'],
    ['signals.captureAppearances','Number of captures containing this account','Bu hesabın göründüğü yakalama sayısı','包含此账户的采集次数','Число снимков с этим аккаунтом'],
    ['signals.sources','Sources','Kaynaklar','来源','Источники'],
    ['signals.finalProbability','Final model-confidence score','Son model güveni skoru','最终模型置信度分数','Итоговая оценка уверенности модели'],
    ['common.minScore','min score','en düşük skor','最低分','мин. балл'],
    ['common.nameMissing','Name unavailable','İsim bilgisi yok','无姓名信息','Имя недоступно'],
    ['common.modelEstimate','model estimate','model tahmini','模型估计','оценка модели'],
    ['common.yes','Yes','Evet','是','Да'],
    ['common.no','No','Hayır','否','Нет'],
    ['common.available','Available','Mevcut','可用','Доступно'],
    ['common.notFound','Not found','Bulunamadı','未找到','Не найдено'],
    ['common.unknown','Unknown','Bilinmiyor','未知','Неизвестно'],
    ['common.public','Public','Açık','公开','Открытый'],
    ['common.privateProfile','Private profile','Gizli profil','私密资料','Закрытый профиль'],
    ['common.publicProfile','Public profile','Herkese açık profil','公开资料','Открытый профиль'],
    ['common.blueTick','Instagram verification','Instagram mavi tiki','Instagram 认证','Подтверждение Instagram'],
    ['common.hasBlueTick','Instagram verified','Instagram mavi tikli','Instagram 已认证','Подтверждено Instagram'],
    ['common.noBlueTick','No verification badge','Mavi tik yok','无认证标记','Нет отметки'],
    ['common.profileDetails','Profile details','Profil ayrıntısı','资料详情','Сведения о профиле'],
    ['common.ready','Ready','Hazır','就绪','Готово'],
    ['common.dataMissing','Data incomplete','Veri eksik','数据不完整','Данные неполные'],
    ['duration.months','{count} mo','{count} ay','{count} 个月','{count} мес.'],
    ['duration.years','{count} yr','{count} yıl','{count} 年','{count} г.'],
    ['duration.yearsMonths','{years} yr {months} mo','{years} yıl {months} ay','{years} 年 {months} 个月','{years} г. {months} мес.'],
    ['panel.reportPreview','{username} · {count} people\nModel confidence report','{username} · {count} kişi\nModel güveni raporu','{username} · {count} 人\n模型置信度报告','{username} · {count} чел.\nОтчёт об уверенности модели'],
    ['people.openPersonAria','Open details for {username}','{username} ayrıntılarını aç','打开 {username} 的详情','Открыть сведения о {username}'],

                                                                  
    ['tier.verified','Very high confidence','Çok yüksek güven','极高置信度','Очень высокая уверенность'],
    ['tier.high','High confidence','Yüksek güven','高置信度','Высокая уверенность'],
    ['tier.medium','Medium confidence','Orta güven','中等置信度','Средняя уверенность'],
    ['tier.low','Low confidence','Düşük güven','低置信度','Низкая уверенность'],
    ['tier.noise','Insufficient signal','Yetersiz sinyal','信号不足','Недостаточно сигналов'],
    ['tier.unknown','Unknown','Bilinmiyor','未知','Неизвестно'],

                                            
    ['detail.personSummary','PERSON SUMMARY','KİŞİ ÖZETİ','人员摘要','СВОДКА О ЧЕЛОВЕКЕ'],
    ['detail.connectionProbability','Model confidence','Model güveni','模型置信度','Уверенность модели'],
    ['detail.estimateDisclaimer','This is an uncalibrated model-confidence score; it does not prove a follow, friendship, or real-world closeness.','Bu, kalibre edilmemiş bir model güveni skorudur; takip, arkadaşlık veya gerçek hayattaki yakınlığı kanıtlamaz.','这是未经校准的模型置信度分数；不能证明关注、好友关系或现实中的亲密程度。','Это некалиброванная оценка уверенности модели; она не доказывает подписку, дружбу или близость в реальной жизни.'],
    ['detail.why','WHY THIS RESULT?','NEDEN BU SONUÇ?','为何得出此结果？','ПОЧЕМУ ТАКОЙ РЕЗУЛЬТАТ?'],
    ['detail.influencingSignals','Signals affecting model confidence','Model güvenini etkileyen sinyaller','影响模型置信度的信号','Сигналы, влияющие на уверенность модели'],
    ['detail.probabilitySignal','Model signal','Model sinyali','模型信号','Сигнал модели'],
    ['detail.noExtraSignal','No additional model signal was recorded.','Ek model sinyali kaydedilmemiş.','未记录其他模型信号。','Дополнительные сигналы модели не зафиксированы.'],
    ['detail.profileInfo','PROFILE INFORMATION','PROFİL BİLGİLERİ','资料信息','ИНФОРМАЦИЯ О ПРОФИЛЕ'],
    ['detail.profile','Profile','Profil','资料','Профиль'],
    ['detail.badge','Instagram badge','Instagram rozeti','Instagram 标记','Отметка Instagram'],
    ['detail.followers','Followers','Takipçi','粉丝','Подписчики'],
    ['detail.following','Following','Takip','关注中','Подписки'],
    ['detail.posts','Posts','Paylaşım','帖子','Публикации'],
    ['detail.noProfileDetails','No additional profile details were available.','Ek profil ayrıntısı bulunamadı.','没有更多资料详情。','Дополнительных сведений о профиле нет.'],
    ['detail.profileDetails','Profile details','Profil ayrıntısı','资料详情','Сведения о профиле'],
    ['detail.estimateValue','Model score: {score}','Model skoru: {score}','模型分数：{score}','Оценка модели: {score}'],
    ['detail.signalVeryHigh','Very high model confidence','Çok yüksek model güveni','模型置信度极高','Очень высокая уверенность модели'],
    ['detail.signalVeryHighText','The available signals contribute consistently to a very high model-confidence score.','Mevcut sinyaller çok yüksek model güveni skoruna tutarlı biçimde katkı sağlıyor.','现有信号一致地形成了极高的模型置信度分数。','Доступные сигналы согласованно дают очень высокую оценку уверенности модели.'],
    ['detail.signalHighText','Several signals contribute to a high model-confidence score.','Birden fazla sinyal yüksek model güveni skoruna katkı sağlıyor.','多个信号形成了较高的模型置信度分数。','Несколько сигналов дают высокую оценку уверенности модели.'],
    ['detail.signalMediumText','Some signals contribute, but model confidence remains limited.','Bazı sinyaller katkı sağlıyor, ancak model güveni sınırlı kalıyor.','部分信号有所贡献，但模型置信度仍然有限。','Некоторые сигналы учитываются, но уверенность модели остаётся ограниченной.'],
    ['detail.signalLowText','The available signals produce a low model-confidence score.','Mevcut sinyaller düşük model güveni skoru üretiyor.','现有信号形成较低的模型置信度分数。','Доступные сигналы дают низкую оценку уверенности модели.'],
    ['detail.signalNoneText','The available signals are insufficient for a useful model-confidence score.','Mevcut sinyaller anlamlı bir model güveni skoru için yetersiz.','现有信号不足以形成有用的模型置信度分数。','Доступных сигналов недостаточно для полезной оценки уверенности модели.'],
    ['signal.connectionCluster','Connection cluster','Bağlantı kümesi','关联群组','Кластер связей'],
    ['signal.connectionClusterText','Appeared among connection suggestions.','Bağlantı önerileri arasında görüldü.','出现在关联推荐中。','Появился среди рекомендаций связей.'],
    ['signal.repeatedMatch','Repeated match','Tekrarlanan eşleşme','重复匹配','Повторное совпадение'],
    ['signal.repeatedMatchText','Appeared repeatedly across several analysis surfaces.','Birçok analiz alanında tekrar görüldü.','在多个分析区域中重复出现。','Неоднократно появлялся в нескольких областях анализа.'],
    ['signal.topRanks','High in results','Üst sıralarda','结果排名靠前','Высоко в результатах'],
    ['signal.topRanksText','Ranked highly in repeated discovery results.','Tekrarlı keşif sonuçlarında güçlü sırada çıktı.','在重复发现结果中排名靠前。','Занял высокое место в повторных результатах поиска.'],
    ['signal.midRanks','Middle of results','Orta sıralarda','结果排名居中','В середине результатов'],
    ['signal.midRanksText','Appeared in the middle of repeated discovery results.','Tekrarlı keşif sonuçlarında orta sırada çıktı.','在重复发现结果中排名居中。','Появился в середине повторных результатов поиска.'],
    ['signal.lowRanks','Low in results','Alt sıralarda','结果排名靠后','Низко в результатах'],
    ['signal.lowRanksText','Appeared far down in repeated discovery results.','Tekrarlı keşif sonuçlarında uzak sırada çıktı.','在重复发现结果中排名靠后。','Появился далеко внизу повторных результатов поиска.'],
    ['signal.generalSuggestion','General suggestion','Genel öneri','普通推荐','Общая рекомендация'],
    ['signal.generalSuggestionText','Appeared only among general suggestions.','Yalnızca genel öneriler arasında görüldü.','仅出现在普通推荐中。','Появился только среди общих рекомендаций.'],
    ['signal.instagramSuggestion','Instagram suggestion','Instagram önerisi','Instagram 推荐','Рекомендация Instagram'],
    ['signal.instagramSuggestionText','Appeared in search or people suggestions.','Arama veya kişi önerileri arasında görüldü.','出现在搜索或人员推荐中。','Появился в поиске или рекомендациях людей.'],
    ['signal.twoWay','Two-way trace','İki yönlü iz','双向痕迹','Двусторонний след'],
    ['signal.twoWayText','Appeared in both directions of the connection chain.','Bağlantı zincirinde iki yönde de görüldü.','在关联链的两个方向均出现。','Появился в обоих направлениях цепочки связей.'],
    ['signal.follow','Test-account follow status','Test hesabının takip durumu','测试账户关注状态','Статус подписки тестового аккаунта'],
    ['signal.followText','The signed-in test account follows this account.','Giriş yapılan test hesabı bu hesabı takip ediyor.','已登录的测试账户关注此账户。','Тестовый аккаунт подписан на этот аккаунт.'],
    ['signal.follower','Test-account follower status','Test hesabının takipçi durumu','测试账户粉丝状态','Статус подписчика тестового аккаунта'],
    ['signal.followerText','This account follows the signed-in test account.','Bu hesap giriş yapılan test hesabını takip ediyor.','此账户关注已登录的测试账户。','Этот аккаунт подписан на тестовый аккаунт.'],
    ['signal.likes','Like interaction','Beğeni etkileşimi','点赞互动','Взаимодействие лайками'],
    ['signal.likesText','Like activity was found on posts.','Gönderilerde beğeni etkileşimi bulundu.','在帖子中发现点赞互动。','Найдены взаимодействия лайками в публикациях.'],
    ['signal.comments','Comment interaction','Yorum etkileşimi','评论互动','Взаимодействие комментариями'],
    ['signal.commentsText','Comment activity was found on posts.','Gönderilerde yorum etkileşimi bulundu.','在帖子中发现评论互动。','Найдены взаимодействия комментариями в публикациях.'],
    ['signal.coTags','Co-tagged','Birlikte etiket','共同标记','Совместная отметка'],
    ['signal.coTagsText','Both accounts were tagged in the same content.','Aynı içerikte birlikte etiketlendiler.','两个账户被标记在同一内容中。','Оба аккаунта отмечены в одном материале.'],
    ['signal.tags','Tag interaction','Etiket etkileşimi','标记互动','Взаимодействие отметками'],
    ['signal.tagsText','A connection trace was found through tags.','Etiket üzerinden bir bağlantı izi bulundu.','通过标记发现关联痕迹。','Через отметки найден след связи.'],
    ['signal.notification','Notification trace','Bildirim izi','通知痕迹','След уведомления'],
    ['signal.notificationText','A shared interaction appeared in notifications.','Bildirimlerde ortak bir etkileşim görüldü.','通知中出现共同互动。','В уведомлениях обнаружено общее взаимодействие.'],
    ['signal.shareSuggestion','Share suggestion','Paylaşım önerisi','分享推荐','Рекомендация отправки'],
    ['signal.shareSuggestionText','Appeared in the share ranking.','Paylaşım sıralamasında görüldü.','出现在分享排序中。','Появился в рейтинге отправки.'],
    ['signal.supporting','Supporting signal','Destekleyici sinyal','支持信号','Подтверждающий сигнал'],
    ['signal.supportingText','A match was found during analysis.','Analiz sırasında bir eşleşme bulundu.','分析期间发现匹配。','Во время анализа найдено совпадение.'],
    ['signal.mutualFollowers','Followers shared with the test account','Test hesabıyla ortak takipçi','与测试账户共同的粉丝','Общие подписчики с тестовым аккаунтом'],
    ['signal.request','Follow request','Takip isteği','关注请求','Запрос на подписку'],
    ['signal.closeFriend','Close friend','Yakın arkadaş','密友','Близкий друг'],
    ['signal.favorite','Favorite account','Favori hesap','收藏账户','Избранный аккаунт'],
    ['signal.muted','Muted','Sessize alınmış','已静音','Без звука'],
    ['signal.restricted','Restricted','Sınırlandırılmış','受限','Ограничен'],

                            
    ['report.noneTitle','No report yet','Henüz rapor yok','暂无报告','Отчёта пока нет'],
    ['report.noneText','Search for a username first.','Önce bir kullanıcıyı sorgulayın.','请先查询用户名。','Сначала выполните поиск пользователя.'],
    ['report.peopleCaptured','People found','Yakalanan kişi','找到的人员','Найдено людей'],
    ['report.fullList','Full result list','Tam sonuç listesi','完整结果列表','Полный список результатов'],
    ['report.analysisTitle','RELATIONSHIP ANALYSIS REPORT','İLİŞKİ ANALİZİ RAPORU','关联分析报告','ОТЧЁТ ОБ АНАЛИЗЕ СВЯЗЕЙ'],
    ['report.lastAnalysis','Last analysis','Son analiz','上次分析','Последний анализ'],
    ['report.disclaimerTitle','Scores are model estimates.','Skorlar model tahminidir.','分数为模型估计。','Оценки рассчитаны моделью.'],
    ['report.disclaimerText','They do not by themselves prove friendship, following, or real-world closeness.','Arkadaşlık, takip veya gerçek hayattaki yakınlığı tek başına kanıtlamaz.','它们本身不能证明好友、关注或现实中的亲密关系。','Сами по себе они не доказывают дружбу, подписку или близость в реальной жизни.'],
    ['report.probabilitySummary','MODEL CONFIDENCE SUMMARY','MODEL GÜVENİ ÖZETİ','模型置信度摘要','СВОДКА УВЕРЕННОСТИ МОДЕЛИ'],
    ['report.networkImage','NETWORK VIEW','AĞ GÖRÜNTÜSÜ','网络视图','СЕТЕВАЯ КАРТА'],
    ['report.graphAria','Network view showing {count} scored model candidates','{count} skorlu model adayını gösteren ağ görünümü','显示 {count} 个已评分模型候选的网络视图','Сетевая карта с {count} оценёнными моделью кандидатами'],
    ['report.realData','Scored model candidates','Skorlu model adayları','已评分模型候选','Оценённые моделью кандидаты'],
    ['report.networkCaption','The target is centered; higher model scores are closer to the center. Lines are candidate links computed from recommendation signals and do not confirm follows.','Hedef merkezde; daha yüksek model skorları merkeze daha yakındır. Çizgiler öneri sinyallerinden hesaplanan aday bağlantılardır ve takip ilişkisini doğrulamaz.','目标位于中心；模型分数越高，越靠近中心。连线是根据推荐信号计算出的候选关联，不能确认关注关系。','Цель находится в центре; более высокие оценки модели расположены ближе к центру. Линии — кандидаты, рассчитанные по сигналам рекомендаций, и они не подтверждают подписку.'],
    ['report.queriedPerson','QUERIED PERSON','SORGULANAN KİŞİ','查询对象','ИСКОМЫЙ ЧЕЛОВЕК'],
    ['report.profileSummary','Profile summary','Profil özeti','资料摘要','Сводка профиля'],
    ['report.sourceNote','Only information actually obtained in the latest analysis is shown. No conclusions are drawn from empty fields.','Yalnızca son analizde gerçekten alınabilen bilgiler gösterilir. Boş alanlardan sonuç çıkarılmaz.','仅显示最近分析中实际获取的信息，不会根据空字段作出推断。','Показываются только сведения, действительно полученные в последнем анализе. По пустым полям выводы не делаются.'],
    ['report.signalEyebrow','SIGNALS AFFECTING THE CONNECTION','BAĞLANTIYI ETKİLEYEN İŞARETLER','影响关联的信号','СИГНАЛЫ, ВЛИЯЮЩИЕ НА СВЯЗЬ'],
    ['report.frequentSignals','Most frequent signals','En sık görülen sinyaller','最常见信号','Самые частые сигналы'],
    ['report.signalCountHelp','The number shows how many different people had this signal.','Rakam, bu işaretin kaç farklı kişide bulunduğunu gösterir.','数字表示有多少不同人员出现此信号。','Число показывает, у скольких разных людей найден этот сигнал.'],
    ['report.capturedInfo','CAPTURED INFORMATION','YAKALANAN BİLGİLER','已获取信息','ПОЛУЧЕННЫЕ СВЕДЕНИЯ'],
    ['report.peopleAndProbability','People and model confidence','Kişiler ve model güveni','人员与模型置信度','Люди и уверенность модели'],
    ['report.level','Confidence level','Güven düzeyi','置信度等级','Уровень уверенности'],
    ['report.foundSignals','Found signals','Bulunan işaretler','发现的信号','Найденные сигналы'],
    ['report.rowHelp','Select a row to see the person’s details and short signal explanations. People with the same score have no definitive order.','Bir kişinin ayrıntılarını ve kısa sinyal açıklamalarını görmek için satıra tıklayın. Aynı skoru alan kişiler arasında kesin bir sıralama yoktur.','点击行可查看人员详情和简短信号说明。分数相同的人员没有确定排序。','Нажмите строку, чтобы увидеть сведения и краткие объяснения сигналов. У людей с одинаковой оценкой нет точного порядка.'],
    ['report.probabilityDefinition','Model score','Model skoru','模型分数','Оценка модели'],
    ['report.probabilityDefinitionText','An uncalibrated 0–100 confidence score derived from signal weights; it is not a probability percentage.','Sinyal ağırlıklarından üretilen, kalibre edilmemiş 0–100 güven skorudur; olasılık yüzdesi değildir.','根据各信号权重得出的未经校准的 0–100 置信度分数；并非概率百分比。','Некалиброванная оценка уверенности 0–100, полученная из весов сигналов; это не процент вероятности.'],
    ['report.signalDefinition','Signal','Sinyal','信号','Сигнал'],
    ['report.signalDefinitionText','A clue supporting the estimate, such as a suggestion, repeated appearance, or interaction.','Öneri, tekrar görünme veya etkileşim gibi tahmini destekleyen işaret.','支持估计的线索，例如推荐、重复出现或互动。','Признак в поддержку оценки: рекомендация, повторное появление или взаимодействие.'],
    ['report.limitDefinition','Limit','Sınır','限制','Ограничение'],
    ['report.limitDefinitionText','Missing or uncollected information does not mean “no connection.”','Görünmeyen veya toplanmayan bilgi, “bağlantı yok” anlamına gelmez.','不可见或未收集的信息并不代表“没有关联”。','Невидимые или несобранные данные не означают «связи нет».'],
    ['report.noBasicInfo','Basic profile information was limited in this analysis.','Bu analizde temel profil bilgisi sınırlı.','本次分析中的基本资料信息有限。','В этом анализе мало основных сведений о профиле.'],
    ['report.noSignals','No additional explainable signal was found in these results.','Bu sonuçlarda açıklanabilir ek sinyal bulunamadı.','这些结果中未发现其他可解释信号。','В этих результатах не найдено дополнительных объяснимых сигналов.'],
    ['report.noPeople','No people were found in this analysis.','Bu analizde kişi bulunamadı.','本次分析未找到人员。','В этом анализе люди не найдены.'],
    ['report.noExtraSignal','No extra signal','Ek sinyal yok','无额外信号','Нет дополнительных сигналов'],

                                
    ['target.hero','TARGET PROFILE','HEDEF PROFİL','目标资料','ЦЕЛЕВОЙ ПРОФИЛЬ'],
    ['target.latestData','Information is shown from the latest completed analysis.','Bilgiler son tamamlanan analiz çıktısından gösteriliyor.','信息来自最近完成的分析。','Показаны сведения из последнего завершённого анализа.'],
    ['target.sectionProfile','Profile and account','Profil ve hesap','资料与账户','Профиль и аккаунт'],
    ['target.sectionProfileText','Visible profile information and account history.','Profilde görünen bilgiler ve hesap geçmişi.','可见资料信息和账户历史。','Видимые данные профиля и история аккаунта.'],
    ['target.sectionLinks','Connections','Bağlantılar','关联','Связи'],
    ['target.sectionLinksText','Follow, message, and platform information relative to your signed-in account.','Giriş yaptığınız hesaba göre takip, mesaj ve platform bilgileri.','相对于当前登录账户的关注、消息和平台信息。','Сведения о подписках, сообщениях и платформах относительно вашего аккаунта.'],
    ['target.sectionSignals','Profile signals','Profil sinyalleri','资料信号','Сигналы профиля'],
    ['target.sectionSignalsText','Technical timestamps, counts, and approximate network-region clues.','Teknik zamanlar, sayılar ve yaklaşık ağ bölgesi işaretleri.','技术时间戳、数量和大致网络区域线索。','Техническое время, счётчики и примерные признаки региона сети.'],
    ['target.sectionExtra','Additional findings','Ek bulgular','其他发现','Дополнительные сведения'],
    ['target.sectionExtraText','Feature availability, candidate links, and technical identifiers.','Özellik kullanılabilirliği, aday bağlantılar ve teknik kimlikler.','功能可用性、候选链接和技术标识符。','Доступность функций, возможные ссылки и технические идентификаторы.'],
    ['target.profileInfo','Profile information','Profil bilgileri','资料信息','Информация профиля'],
    ['target.profileInfoText','Basic account information explicitly visible in the Instagram response.','Instagram yanıtında açıkça görülen temel hesap bilgileri.','Instagram 响应中明确可见的基本账户信息。','Основные сведения аккаунта, явно видимые в ответе Instagram.'],
    ['target.history','Account history','Hesap geçmişi','账户历史','История аккаунта'],
    ['target.historyText','Account-history information provided under the EU platform-transparency framework.','DSA, Avrupa Birliği’nin platform şeffaflığı kapsamında sunulan hesap geçmişidir.','欧盟平台透明度框架下提供的账户历史信息。','История аккаунта, предоставляемая в рамках требований ЕС о прозрачности платформ.'],
    ['target.stories','Stories and highlights','Hikâyeler ve öne çıkanlar','快拍与精选','Истории и актуальное'],
    ['target.storiesText','Only story and highlight summaries accessible during this analysis.','Yalnızca analiz sırasında erişilebilen hikâye ve öne çıkan özetleri.','仅显示本次分析期间可访问的快拍和精选摘要。','Только сводки историй и актуального, доступные во время анализа.'],
    ['target.bioLinks','Bio links','Biyografi bağlantıları','简介链接','Ссылки в описании'],
    ['target.bioLinksText','External links published on the account profile.','Hesabın profilinde yayımlanan dış bağlantılar.','账户资料中发布的外部链接。','Внешние ссылки, опубликованные в профиле аккаунта.'],
    ['target.followLink','Follow connection','Takip bağlantısı','关注关系','Связь подписки'],
    ['target.followLinkText','Follow status between your signed-in account and the target.','Giriş yaptığınız hesap ile hedef arasındaki takip durumu.','当前登录账户与目标之间的关注状态。','Статус подписки между вашим аккаунтом и целью.'],
    ['target.relationship','Connection to you','Sizinle bağlantısı','与您的关联','Связь с вами'],
    ['target.relationshipText','“You” means the Instagram account signed in to this application.','“Siz”, uygulamada Instagram’a giriş yapılmış hesabı ifade eder.','“您”指本应用中登录的 Instagram 账户。','«Вы» означает аккаунт Instagram, используемый для входа в приложение.'],
    ['target.messaging','Messaging status','Mesajlaşma durumu','消息状态','Статус сообщений'],
    ['target.messagingText','This status is relative only to the signed-in account.','Bu durum yalnızca giriş yaptığınız hesabın hedefe göre gördüğü bilgidir.','此状态仅相对于当前登录账户。','Этот статус относится только к аккаунту, используемому для входа.'],
    ['target.birthday','Birthday visibility','Doğum günü görünürlüğü','生日可见性','Видимость дня рождения'],
    ['target.birthdayText','The limited birthday status Instagram exposes to this session.','Instagram’ın bu oturuma gösterdiği sınırlı doğum günü durumu.','Instagram 向当前会话显示的有限生日状态。','Ограниченный статус дня рождения, доступный этому сеансу Instagram.'],
    ['target.threads','Threads profile','Threads profili','Threads 资料','Профиль Threads'],
    ['target.threadsText','Threads is a separate platform; visibility and counts may differ from Instagram.','Threads ayrı bir platformdur; görünürlük ve sayılar Instagram’dan farklı olabilir.','Threads 是独立平台；可见性和数量可能与 Instagram 不同。','Threads — отдельная платформа; видимость и числа могут отличаться от Instagram.'],
    ['target.recovery','Account recovery options','Hesap kurtarma seçenekleri','账户恢复选项','Варианты восстановления'],
    ['target.recoveryText','Methods masked by Instagram; these are not full contact details.','Instagram’ın maskeleyerek gösterdiği yöntemlerdir; tam iletişim bilgisi değildir.','Instagram 脱敏显示的方法，并非完整联系方式。','Способы, показанные Instagram в скрытом виде; это не полные контактные данные.'],
    ['target.avatarSignals','Profile-photo signals','Profil fotoğrafı sinyalleri','头像信号','Сигналы фото профиля'],
    ['target.avatarSignalsText','Time and ownership clues derived from the photo content identifier.','Fotoğrafın içerik kimliğinden çıkarılan zaman ve sahiplik işaretleri.','从头像内容标识符推导的时间和归属线索。','Признаки времени и принадлежности, полученные из идентификатора фото.'],
    ['target.geo','Approximate network region','Yaklaşık bölge tahmini','大致网络区域','Примерный регион сети'],
    ['target.geoText','Several weak clues are combined; none is proof of location on its own.','Birden fazla zayıf işaret birlikte değerlendirilir; tek başına hiçbiri konum kanıtı değildir.','综合多个弱线索；任何单一线索都不能证明位置。','Объединяются несколько слабых признаков; ни один из них сам по себе не доказывает местоположение.'],
    ['target.extraCounts','Other profile counts','Diğer profil sayıları','其他资料数量','Другие счётчики профиля'],
    ['target.extraCountsText','Additional counts from different Instagram responses; they may not have updated at the same time.','Farklı Instagram yanıtlarında bulunan ek sayılar; aynı anda güncellenmemiş olabilir.','来自不同 Instagram 响应的额外数量；更新时间可能不同。','Дополнительные числа из разных ответов Instagram; они могли обновиться в разное время.'],
    ['target.features','Instagram features','Instagram özellikleri','Instagram 功能','Функции Instagram'],
    ['target.featuresText','These indicators show that a feature may be available; they do not always prove the user enabled it.','Bu göstergeler bir özelliğin sunulabildiğini gösterir; kullanıcının seçimini her zaman kanıtlamaz.','这些指标表示功能可能可用，但不一定证明用户已启用。','Эти признаки показывают доступность функции, но не всегда доказывают, что пользователь её включил.'],
    ['target.facebook','Possible Facebook links','Olası Facebook bağlantıları','可能的 Facebook 链接','Возможные ссылки Facebook'],
    ['target.technical','Technical identifiers and network information','Teknik kimlikler ve ağ bilgisi','技术标识符与网络信息','Технические идентификаторы и сеть'],
    ['target.technicalText','These numbers and server indicators are for application operation; they are not proof of a personal profile or location.','Bu numara ve sunucu işaretleri uygulamanın çalışması içindir; kişisel profil veya konum kanıtı değildir.','这些编号和服务器指标用于应用运行，并非个人资料或位置证据。','Эти номера и серверные признаки нужны для работы приложения; они не доказывают профиль или местоположение.'],
    ['target.networkStatuses','Statuses in the test account’s suggestion network','Test hesabının öneri ağındaki durumlar','测试账户推荐网络中的状态','Статусы в сети рекомендаций тестового аккаунта'],
    ['target.networkStatusesText','This is not a list of the target’s friends; it only shows statuses relative to the signed-in test account’s suggestion set.','Bu liste hedefin arkadaşları değildir; yalnızca giriş yapılan test hesabının öneri kümesine göre durumları gösterir.','这不是目标的好友列表；仅显示相对于已登录测试账户推荐集合的状态。','Это не список друзей цели; показаны только статусы относительно рекомендаций тестового аккаунта.'],
    ['target.definiteLocation','Not an exact location','Kesin konum değildir','并非精确位置','Это не точное местоположение'],
    ['target.geoMethod','This estimate combines time, bio, tags, and related-network language clues.','Saat, biyografi, etiket ve ilişkili ağın dili gibi işaretlerin birleşiminden oluşan tahmindir.','该估计综合了时间、简介、标记和关联网络语言等线索。','Оценка объединяет время, описание, отметки и язык связанной сети.'],
    ['target.relativeScores','These scores are relative weights, not probability percentages.','Bu skorlar olasılık yüzdesi değildir; farklı işaretlerin göreli ağırlığıdır.','这些分数是相对权重，并非概率百分比。','Это относительные веса, а не проценты вероятности.'],
    ['target.technicalShow','Show technical values','Teknik değerleri göster','显示技术值','Показать технические значения'],

                                                                              
                                                             
    ['country.tr','Türkiye','Türkiye','土耳其','Турция'],
    ['country.gr','Greece','Yunanistan','希腊','Греция'],
    ['country.eg','Egypt','Mısır','埃及','Египет'],
    ['country.il','Israel','İsrail','以色列','Израиль'],
    ['country.za','South Africa','Güney Afrika','南非','Южная Африка'],
    ['country.de','Germany','Almanya','德国','Германия'],
    ['country.fr','France','Fransa','法国','Франция'],
    ['country.it','Italy','İtalya','意大利','Италия'],
    ['country.es','Spain','İspanya','西班牙','Испания'],
    ['country.pt','Portugal','Portekiz','葡萄牙','Португалия'],
    ['country.gb','United Kingdom','Birleşik Krallık','英国','Великобритания'],
    ['country.us','United States','ABD','美国','США'],
    ['country.ca','Canada','Kanada','加拿大','Канада'],
    ['country.sa','Saudi Arabia','Suudi Arabistan','沙特阿拉伯','Саудовская Аравия'],
    ['country.ruMoscow','Russia (Moscow)','Rusya (Moskova)','俄罗斯（莫斯科）','Россия (Москва)'],
    ['region.eastAfrica','East Africa','Doğu Afrika','东非','Восточная Африка'],
    ['country.is','Iceland','İzlanda','冰岛','Исландия'],
    ['region.westAfrica','West Africa','Batı Afrika','西非','Западная Африка'],
    ['country.ar','Argentina','Arjantin','阿根廷','Аргентина'],
    ['country.br','Brazil (BR)','Brezilya (BR)','巴西（BR）','Бразилия (BR)'],
    ['country.sr','Suriname','Surinam','苏里南','Суринам'],
    ['region.usEast','US East','ABD Doğu','美国东部','Восток США'],
    ['region.caEast','Canada East','Kanada Doğu','加拿大东部','Восток Канады'],
    ['country.co','Colombia','Kolombiya','哥伦比亚','Колумбия'],
    ['country.pe','Peru','Peru','秘鲁','Перу'],
    ['region.usPacific','US Pacific','ABD Pasifik','美国太平洋地区','Тихоокеанский регион США'],
    ['region.caWest','Canada West','Kanada Batı','加拿大西部','Запад Канады'],
    ['country.pk','Pakistan','Pakistan','巴基斯坦','Пакистан'],
    ['country.mv','Maldives','Maldivler','马尔代夫','Мальдивы'],
    ['country.in','India','Hindistan','印度','Индия'],
    ['country.lk','Sri Lanka','Sri Lanka','斯里兰卡','Шри-Ланка'],
    ['country.cn','China','Çin','中国','Китай'],
    ['country.sg','Singapore','Singapur','新加坡','Сингапур'],
    ['country.ph','Philippines','Filipinler','菲律宾','Филиппины'],
    ['region.auPerth','Australia (Perth)','Avustralya (Perth)','澳大利亚（珀斯）','Австралия (Перт)'],
    ['country.jp','Japan','Japonya','日本','Япония'],
    ['country.kr','Korea','Kore','韩国','Корея'],
    ['region.auEast','Australia East','Avustralya Doğu','澳大利亚东部','Восток Австралии'],
    ['region.eu','European Union','Avrupa Birliği','欧盟','Европейский союз'],
    ['country.nl','Netherlands','Hollanda','荷兰','Нидерланды'],
    ['country.ru','Russia','Rusya','俄罗斯','Россия'],
    ['country.ua','Ukraine','Ukrayna','乌克兰','Украина'],
    ['country.az','Azerbaijan','Azerbaycan','阿塞拜疆','Азербайджан'],
    ['country.ir','Iran','İran','伊朗','Иран'],
    ['country.ae','United Arab Emirates','Birleşik Arap Emirlikleri','阿拉伯联合酋长国','Объединённые Арабские Эмираты'],
    ['region.easternEurope','Eastern Europe','Doğu Avrupa','东欧','Восточная Европа'],
    ['region.centralEurope','Central Europe','Orta Avrupa','中欧','Центральная Европа'],

                                             
    ['status.accountsLoading','Loading saved accounts…','Kayıtlı hesaplar yükleniyor…','正在加载已保存账户…','Загрузка сохранённых аккаунтов…'],
    ['status.scoresUpdated','Scores updated','Skorlar yenilendi','分数已更新','Оценки обновлены'],
    ['status.scoresFailed','Scores could not be updated','Skorlar yenilenemedi','无法更新分数','Не удалось обновить оценки'],
    ['status.staleBlocked','A stale response for another account was blocked; try again.','Başka hesaba ait eski yanıt engellendi; yeniden deneyin.','已阻止另一个账户的过期响应；请重试。','Устаревший ответ другого аккаунта заблокирован; повторите попытку.'],
    ['status.usernameRequired','A username is required','Kullanıcı adı gerekli','请输入用户名','Требуется имя пользователя'],
    ['status.usernameInvalid','Invalid username','Geçersiz kullanıcı adı','用户名无效','Недопустимое имя пользователя'],
    ['status.choosePhase','Select at least one analysis section','En az bir analiz bölümü seçin','请至少选择一个分析模块','Выберите хотя бы один раздел анализа'],
    ['status.scoringDone','Model-confidence scores calculated','Model güveni skorları hesaplandı','模型置信度分数已计算','Оценки уверенности модели рассчитаны'],
    ['status.scoringFailed','Scoring could not be completed','Skorlama tamamlanamadı','无法完成评分','Не удалось завершить оценку'],
    ['status.serverLost','Server connection lost','Sunucu bağlantısı kesildi','服务器连接中断','Соединение с сервером потеряно'],
    ['status.analysisStopped','Analysis stopped','Analiz durduruldu','分析已停止','Анализ остановлен'],
    ['status.initError','Initialization error: {message}','Başlatma hatası: {message}','初始化错误：{message}','Ошибка запуска: {message}'],
    ['log.started','Analysis started','Analiz başlatıldı','分析已开始','Анализ запущен'],
    ['log.collecting','Collecting data for the account.','Hesap için veriler toplanıyor.','正在收集账户数据。','Собираются данные аккаунта.'],
    ['log.fastOn','Fast scan enabled','Hızlı tarama açık','已启用快速扫描','Включено быстрое сканирование'],
    ['log.fastOnText','Slow or frequently failing extra checks are skipped.','Yavaş veya sık başarısız olan ek kontroller atlanıyor.','跳过缓慢或经常失败的额外检查。','Медленные или часто неудачные дополнительные проверки пропускаются.'],
    ['log.deepOn','Detailed scan enabled','Ayrıntılı tarama açık','已启用详细扫描','Включено подробное сканирование'],
    ['log.deepOnText','All selected checks are running.','Seçilen bütün kontroller çalıştırılıyor.','正在运行所有已选检查。','Выполняются все выбранные проверки.'],
    ['log.profilePreparing','Preparing profile','Profil hazırlanıyor','正在准备资料','Подготовка профиля'],
    ['log.profilePreparingText','Locating the Instagram profile identifier.','Instagram profil kimliği bulunuyor.','正在查找 Instagram 资料标识符。','Поиск идентификатора профиля Instagram.'],
    ['log.profileFound','Profile record found','Profil kaydı bulundu','已找到资料记录','Запись профиля найдена'],
    ['log.profileFoundText','Checks started with the saved profile identifier.','Kayıtlı profil kimliğiyle kontroller başlatıldı.','已使用保存的资料标识符开始检查。','Проверки запущены с сохранённым идентификатором профиля.'],
    ['log.profileMissing','Profile not found','Profil bulunamadı','未找到资料','Профиль не найден'],
    ['log.profileMissingText','Check the username, session, or Instagram access.','Kullanıcı adı, oturum veya Instagram erişimi kontrol edilmeli.','请检查用户名、会话或 Instagram 访问权限。','Проверьте имя пользователя, сеанс или доступ к Instagram.'],
    ['log.sessionLoaded','Session information loaded','Oturum bilgileri yüklendi','会话信息已加载','Данные сеанса загружены'],
    ['log.sessionVerified','Instagram session verified','Instagram oturumu doğrulandı','Instagram 会话已验证','Сеанс Instagram подтверждён'],
    ['log.rateLimited','Instagram temporarily limited requests','Instagram geçici istek sınırı uyguladı','Instagram 暂时限制了请求','Instagram временно ограничил запросы'],
    ['log.rateLimitedText','Wait a few minutes and try again.','Birkaç dakika bekleyip tekrar deneyebilirsiniz.','请等待几分钟后重试。','Подождите несколько минут и повторите попытку.'],
    ['log.authFailed','Instagram session could not be verified','Instagram oturumu doğrulanamadı','无法验证 Instagram 会话','Не удалось подтвердить сеанс Instagram'],
    ['log.timeout','Instagram did not respond in time','Instagram zamanında yanıt vermedi','Instagram 未及时响应','Instagram не ответил вовремя'],
    ['log.collectionDone','Data collection completed','Veri toplama tamamlandı','数据收集完成','Сбор данных завершён'],
    ['log.collectionFailed','Data collection could not be completed','Veri toplama tamamlanamadı','无法完成数据收集','Не удалось завершить сбор данных'],
    ['log.scoringDone','Model-confidence scores calculated','Model güveni skorları hesaplandı','模型置信度分数已计算','Оценки уверенности модели рассчитаны'],
    ['log.resultsPreparing','Preparing results','Sonuçlar hazırlanıyor','正在准备结果','Подготовка результатов'],
    ['log.resultsPreparingText','Loading new data safely into the interface.','Yeni veriler ekrana güvenli biçimde yükleniyor.','正在将新数据安全加载到界面。','Новые данные безопасно загружаются в интерфейс.'],
    ['log.reloadFailed','Result view could not be refreshed','Sonuç ekranı yenilenemedi','无法刷新结果视图','Не удалось обновить экран результатов'],
    ['log.cancelled','Analysis stopped','Analiz durduruldu','分析已停止','Анализ остановлен'],
    ['log.connectionLost','Server connection lost','Sunucu bağlantısı kesildi','服务器连接中断','Соединение с сервером потеряно'],
    ['log.genericError','An analysis step could not be completed','Bir analiz adımı tamamlanamadı','某个分析步骤未能完成','Один из этапов анализа не завершён'],
    ['log.ready','Analysis complete','Analiz tamamlandı','分析完成','Анализ завершён'],
  ];

  const catalog = Object.create(null);
  const sourceIndex = new Map();
  for (const [key, en, tr, zh, ru] of entries) {
    const value = {en, tr, 'zh-CN':zh, ru};
    catalog[key] = value;
    for (const phrase of Object.values(value)) sourceIndex.set(normalize(phrase), key);
  }

  const textBindings = new WeakMap();
  const attributeBindings = new WeakMap();
  let currentLocale = readInitialLocale();
  let observer = null;
  let initialized = false;

  function normalize(value) {
    return String(value ?? '').trim().replace(/\s+/g, ' ');
  }

  function normalizeLocale(value) {
    const raw = String(value || '').trim();
    if (SUPPORTED.has(raw)) return raw;
    const lower = raw.toLowerCase();
    if (lower.startsWith('tr')) return 'tr';
    if (lower.startsWith('zh')) return 'zh-CN';
    if (lower.startsWith('ru')) return 'ru';
    return 'en';
  }

  function readInitialLocale() {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? normalizeLocale(stored) : DEFAULT_LOCALE;
    } catch (_) {
      return DEFAULT_LOCALE;
    }
  }

  function formatVariable(key, value, locale=currentLocale) {
    if (value == null) return '';
    if (['count','current','total','visible','rank','found','years','months','hour','depth','sections'].includes(key)) {
                                                                              
                                                                             
                                                     
      const raw = typeof value === 'string' ? value.trim() : value;
      const number = typeof raw === 'number'
        ? raw
        : /^-?\d+$/.test(raw) ? Number(raw) : Number.NaN;
      if (Number.isFinite(number)) {
        return new Intl.NumberFormat(FORMAT_LOCALE[locale] || FORMAT_LOCALE.en).format(number);
      }
    }
    return String(value);
  }

  function interpolate(message, vars={}, locale=currentLocale) {
    return String(message).replace(/\{([a-zA-Z0-9_]+)\}/g, (_, key) =>
      Object.prototype.hasOwnProperty.call(vars, key) ? formatVariable(key, vars[key], locale) : `{${key}}`);
  }

  function t(key, vars={}) {
    const row = catalog[key];
    if (!row) return String(key || '');
    return interpolate(row[currentLocale] || row.en, vars, currentLocale);
  }

  const patterns = [
    [/^(\d+) hesap bulundu$/, 'status.accountsFound', m => ({count:m[1]})],
    [/^(.+?) yükleniyor…$/, 'status.userLoading', m => ({username:m[1]})],
    [/^(.+?) için sonuç bulunamadı$/, 'status.userNotFound', m => ({username:m[1]})],
    [/^(.+?) yüklendi — (\d+) kişi$/, 'status.userLoaded', m => ({username:m[1], count:m[2]})],
    [/^(.+?) için skorlar yenileniyor…$/, 'status.scoresRefreshing', m => ({username:m[1]})],
    [/^(.+?) analiz ediliyor…$/, 'status.analyzing', m => ({username:m[1]})],
    [/^(\d+) \/ (\d+) kişi$/, 'people.visibleCount', m => ({visible:m[1], total:m[2]})],
    [/^View all (\d+) persons$/, 'people.viewAllCount', m => ({count:m[1]})],
    [/^(\d+) skorlu aday haritada$/, 'report.peopleOnMap', m => ({count:m[1]})],
    [/^(\d+) kişi$/, 'common.peopleCount', m => ({count:m[1]})],
    [/^(\d+) kayıt$/, 'common.recordCount', m => ({count:m[1]})],
    [/^(\d+) ek profil özelliği bulundu$/, 'log.extraFields', m => ({count:m[1]})],
    [/^Ağ tarama derinliği: (\d+)$/, 'log.depthValue', m => ({count:m[1]})],
    [/^Bağlantı taraması (\d+)\/(\d+)$/, 'log.scanProgress', m => ({current:m[1], total:m[2]})],
    [/^(\d+) bağlantı adayı bulundu$/, 'log.candidatesFound', m => ({count:m[1]})],
    [/^(\d+) karşılıklı öneri örtüşmesi$/, 'log.mutualFound', m => ({count:m[1]})],
  ];

  Object.assign(catalog, {
    'status.accountsFound':{en:'{count} accounts found',tr:'{count} hesap bulundu','zh-CN':'找到 {count} 个账户',ru:'Найдено аккаунтов: {count}'},
    'status.userLoading':{en:'Loading {username}…',tr:'{username} yükleniyor…','zh-CN':'正在加载 {username}…',ru:'Загрузка {username}…'},
    'status.userNotFound':{en:'No result found for {username}',tr:'{username} için sonuç bulunamadı','zh-CN':'未找到 {username} 的结果',ru:'Для {username} результат не найден'},
    'status.userLoaded':{en:'Loaded {username} — {count} people',tr:'{username} yüklendi — {count} kişi','zh-CN':'已加载 {username} — {count} 人',ru:'Загружен {username} — людей: {count}'},
    'status.scoresRefreshing':{en:'Recalculating scores for {username}…',tr:'{username} için skorlar yenileniyor…','zh-CN':'正在重新计算 {username} 的分数…',ru:'Пересчёт оценок для {username}…'},
    'status.analyzing':{en:'Analyzing {username}…',tr:'{username} analiz ediliyor…','zh-CN':'正在分析 {username}…',ru:'Анализ {username}…'},
    'people.visibleCount':{en:'{visible} / {total} people',tr:'{visible} / {total} kişi','zh-CN':'{visible} / {total} 人',ru:'{visible} / {total} чел.'},
    'people.viewAllCount':{en:'View all {count} people',tr:'{count} kişinin tümünü göster','zh-CN':'查看全部 {count} 人',ru:'Показать всех: {count}'},
    'report.peopleOnMap':{en:'{count} scored candidates on the map',tr:'{count} skorlu aday haritada','zh-CN':'图中有 {count} 个已评分候选','ru':'На карте оценённых кандидатов: {count}'},
    'common.peopleCount':{en:'{count} people',tr:'{count} kişi','zh-CN':'{count} 人',ru:'Людей: {count}'},
    'common.recordCount':{en:'{count} records',tr:'{count} kayıt','zh-CN':'{count} 条记录',ru:'Записей: {count}'},
    'common.contentCount':{en:'{count} items',tr:'{count} içerik','zh-CN':'{count} 项内容',ru:'Материалов: {count}'},
    'log.extraFields':{en:'{count} additional profile fields found',tr:'{count} ek profil özelliği bulundu','zh-CN':'发现 {count} 个额外资料字段',ru:'Найдено дополнительных полей: {count}'},
    'log.depthValue':{en:'Network scan depth: {count}',tr:'Ağ tarama derinliği: {count}','zh-CN':'网络扫描深度：{count}',ru:'Глубина сканирования сети: {count}'},
    'log.scanProgress':{en:'Connection scan {current}/{total}',tr:'Bağlantı taraması {current}/{total}','zh-CN':'关联扫描 {current}/{total}',ru:'Сканирование связей {current}/{total}'},
    'log.candidatesFound':{en:'{count} connection candidates found',tr:'{count} bağlantı adayı bulundu','zh-CN':'找到 {count} 个关联候选',ru:'Найдено кандидатов: {count}'},
    'log.mutualFound':{en:'{count} reciprocal recommendation overlaps',tr:'{count} karşılıklı öneri örtüşmesi','zh-CN':'{count} 个双向推荐重合','ru':'Взаимных пересечений рекомендаций: {count}'},
  });

  Object.assign(catalog, {
                                          
    'common.present':{en:'Yes',tr:'Var','zh-CN':'有',ru:'Есть'},
    'common.absent':{en:'No',tr:'Yok','zh-CN':'无',ru:'Нет'},
    'common.visible':{en:'Visible',tr:'Görünüyor','zh-CN':'可见',ru:'Видно'},
    'common.notVisible':{en:'Not visible',tr:'Görülmedi','zh-CN':'不可见',ru:'Не видно'},
    'common.shown':{en:'Shown',tr:'Gösteriliyor','zh-CN':'显示',ru:'Показывается'},
    'common.notShown':{en:'Not shown',tr:'Gösterilmiyor','zh-CN':'不显示',ru:'Не показывается'},
    'common.availableShort':{en:'Available',tr:'Mevcut','zh-CN':'可用',ru:'Доступно'},
    'common.everyone':{en:'Public',tr:'Herkese açık','zh-CN':'公开',ru:'Открытый'},
    'common.details':{en:'Details',tr:'Ayrıntılar','zh-CN':'详情',ru:'Подробности'},
    'common.recordPresent':{en:'Record found',tr:'Kayıt var','zh-CN':'有记录',ru:'Запись найдена'},
    'common.recordAbsent':{en:'No record',tr:'Kayıt yok','zh-CN':'无记录',ru:'Записи нет'},
    'common.untitled':{en:'Untitled',tr:'Başlıksız','zh-CN':'无标题',ru:'Без названия'},
    'common.publicProfileAlt':{en:'Public profile',tr:'Açık profil','zh-CN':'公开资料','ru':'Открытый профиль'},
    'common.sampleSize':{en:'sample size',tr:'örnek sayısı','zh-CN':'样本量',ru:'размер выборки'},
    'common.noValidScore':{en:'No valid model score',tr:'Geçerli model skoru yok','zh-CN':'无有效模型分数',ru:'Нет действительной оценки модели'},
    'common.modelScoreValue':{en:'{score}/100 model score',tr:'{score}/100 model skoru','zh-CN':'模型分数 {score}/100',ru:'Оценка модели: {score}/100'},
    'common.modelConfidenceScore':{en:'model-confidence score',tr:'model güveni skoru','zh-CN':'模型置信度分数',ru:'оценка уверенности модели'},

    'detail.analysisRank':{en:'Analysis rank',tr:'Analizdeki sıra','zh-CN':'分析排名',ru:'Место в анализе'},
    'detail.signalHigh':{en:'High model confidence',tr:'Yüksek model güveni','zh-CN':'高模型置信度',ru:'Высокая уверенность модели'},
    'detail.signalMedium':{en:'Medium model confidence',tr:'Orta model güveni','zh-CN':'中等模型置信度',ru:'Средняя уверенность модели'},
    'detail.signalLow':{en:'Low model confidence',tr:'Düşük model güveni','zh-CN':'低模型置信度',ru:'Низкая уверенность модели'},
    'detail.signalInsufficient':{en:'Insufficient signal',tr:'Yetersiz sinyal','zh-CN':'信号不足',ru:'Недостаточно сигналов'},
    'detail.signalUnknownText':{en:'No valid model score was produced, so no confidence tier is assigned.',tr:'Geçerli model skoru üretilemedi; bu nedenle güven düzeyi atanmadı.','zh-CN':'未生成有效模型分数，因此未分配置信度等级。',ru:'Действительная оценка модели не получена, поэтому уровень уверенности не назначен.'},
    'detail.viewerFollowInfo':{en:'Signed-in test account follow status',tr:'Giriş yapılan test hesabının takip durumu','zh-CN':'已登录测试账户的关注状态',ru:'Статус подписки тестового аккаунта'},
    'detail.signedInFollowsAccount':{en:'The signed-in test account follows this account.','tr':'Giriş yapılan test hesabı bu hesabı takip ediyor.','zh-CN':'已登录的测试账户关注此账户。',ru:'Тестовый аккаунт подписан на этот аккаунт.'},
    'detail.accountFollowsSignedIn':{en:'This account follows the signed-in test account.',tr:'Bu hesap giriş yapılan test hesabını takip ediyor.','zh-CN':'此账户关注已登录的测试账户。',ru:'Этот аккаунт подписан на тестовый аккаунт.'},
    'detail.viewerFollowRequest':{en:'Signed-in test account follow request',tr:'Giriş yapılan test hesabının takip isteği','zh-CN':'已登录测试账户的关注请求',ru:'Запрос на подписку тестового аккаунта'},
    'detail.signedInRequestedAccount':{en:'The signed-in test account sent this account a follow request.',tr:'Giriş yapılan test hesabı bu hesaba takip isteği gönderdi.','zh-CN':'已登录的测试账户向此账户发送了关注请求。',ru:'Тестовый аккаунт отправил этому аккаунту запрос на подписку.'},
    'detail.accountRequestedSignedIn':{en:'This account sent the signed-in test account a follow request.',tr:'Bu hesap giriş yapılan test hesabına takip isteği gönderdi.','zh-CN':'此账户向已登录的测试账户发送了关注请求。',ru:'Этот аккаунт отправил тестовому аккаунту запрос на подписку.'},
    'detail.viewerListStatus':{en:'Signed-in test account list status',tr:'Giriş yapılan test hesabının liste durumu','zh-CN':'已登录测试账户的列表状态',ru:'Статус в списках тестового аккаунта'},
    'detail.inSignedInCloseFriends':{en:'This account appears in the signed-in test account’s Close Friends list.',tr:'Bu hesap giriş yapılan test hesabının Yakın Arkadaşlar listesinde görünüyor.','zh-CN':'此账户出现在已登录测试账户的密友列表中。',ru:'Этот аккаунт находится в списке близких друзей тестового аккаунта.'},
    'detail.inSignedInFavorites':{en:'This account appears in the signed-in test account’s Favorites feed.',tr:'Bu hesap giriş yapılan test hesabının Favoriler akışında görünüyor.','zh-CN':'此账户出现在已登录测试账户的收藏动态中。',ru:'Этот аккаунт находится в ленте избранного тестового аккаунта.'},
    'detail.mutedBySignedIn':{en:'The signed-in test account appears to have muted this account.',tr:'Giriş yapılan test hesabı bu hesabı sessize almış görünüyor.','zh-CN':'已登录的测试账户似乎已将此账户静音。',ru:'Похоже, тестовый аккаунт отключил звук для этого аккаунта.'},
    'detail.limitedBySignedIn':{en:'The signed-in test account appears to have blocked or restricted this account.',tr:'Giriş yapılan test hesabı bu hesabı engellemiş veya kısıtlamış görünüyor.','zh-CN':'已登录的测试账户似乎已屏蔽或限制此账户。',ru:'Похоже, тестовый аккаунт заблокировал или ограничил этот аккаунт.'},
    'detail.viewerSharedFollowers':{en:'Followers shared with the signed-in test account',tr:'Giriş yapılan test hesabıyla ortak takipçiler','zh-CN':'与已登录测试账户共同的粉丝',ru:'Общие подписчики с тестовым аккаунтом'},
    'detail.reciprocalSignal':{en:'Reciprocal recommendation overlap',tr:'Karşılıklı öneri örtüşmesi','zh-CN':'双向推荐重合',ru:'Взаимное пересечение рекомендаций'},
    'detail.reciprocalSignalText':{en:'The candidate appeared in both directions of the recommendation-chain scan; this does not prove a follow.',tr:'Aday, öneri zinciri taramasının iki yönünde de görüldü; bu bir takip kanıtı değildir.','zh-CN':'该候选在推荐链扫描的两个方向均出现；这不能证明关注关系。',ru:'Кандидат появился в обоих направлениях цепочки рекомендаций; это не доказывает подписку.'},
    'detail.oneWaySignal':{en:'One-way recommendation-chain overlap',tr:'Tek yönlü öneri zinciri örtüşmesi','zh-CN':'单向推荐链重合',ru:'Одностороннее пересечение цепочки рекомендаций'},
    'detail.oneWayTraceText':{en:'The candidate appeared in only one direction of the recommendation-chain scan; this does not prove a follow.',tr:'Aday, öneri zinciri taramasının yalnız bir yönünde görüldü; bu bir takip kanıtı değildir.','zh-CN':'该候选仅在推荐链扫描的一个方向出现；这不能证明关注关系。',ru:'Кандидат появился только в одном направлении цепочки рекомендаций; это не доказывает подписку.'},
    'detail.instagramPeopleSuggestion':{en:'Appeared in Instagram people suggestions.',tr:'Instagram kişi önerileri arasında görüldü.','zh-CN':'出现在 Instagram 人员推荐中。',ru:'Появился в рекомендациях людей Instagram.'},

    'report.thresholdVerified':{en:'Score 99–100',tr:'Skor 99–100','zh-CN':'分数 99–100',ru:'Оценка 99–100'},
    'report.thresholdHigh':{en:'Score 80–98.9',tr:'Skor 80–98,9','zh-CN':'分数 80–98.9',ru:'Оценка 80–98,9'},
    'report.thresholdMedium':{en:'Score 40–79.9',tr:'Skor 40–79,9','zh-CN':'分数 40–79.9',ru:'Оценка 40–79,9'},
    'report.thresholdLow':{en:'Score 15–39.9',tr:'Skor 15–39,9','zh-CN':'分数 15–39.9',ru:'Оценка 15–39,9'},
    'report.thresholdNoise':{en:'Score below 15 or unavailable',tr:'Skor 15 altı veya yok','zh-CN':'分数低于 15 或不可用',ru:'Оценка ниже 15 или недоступна'},
    'report.verifiedHelp':{en:'The strongest model-confidence tier.','tr':'En güçlü model güveni düzeyi.','zh-CN':'最高模型置信度等级。',ru:'Самый высокий уровень уверенности модели.'},
    'report.highHelp':{en:'Several strong signals were found.',tr:'Birden fazla güçlü işaret bulundu.','zh-CN':'发现多个强信号。',ru:'Найдено несколько сильных сигналов.'},
    'report.mediumHelp':{en:'Supporting signals exist, but the result is limited.',tr:'Destekleyici işaretler var, sonuç sınırlı.','zh-CN':'存在支持信号，但结论有限。',ru:'Есть подтверждающие сигналы, но вывод ограничен.'},
    'report.lowHelp':{en:'Connection signals are weak.',tr:'Bağlantı işaretleri zayıf.','zh-CN':'关联信号较弱。',ru:'Сигналы связи слабы.'},
    'report.noiseHelp':{en:'There is not enough signal to interpret.',tr:'Yorum yapmak için yeterli işaret yok.','zh-CN':'信号不足，无法判断。',ru:'Недостаточно сигналов для вывода.'},
    'report.accountType':{en:'Account type',tr:'Hesap türü','zh-CN':'账户类型',ru:'Тип аккаунта'},
    'report.profileVisibility':{en:'Profile visibility',tr:'Profil görünürlüğü','zh-CN':'资料可见性',ru:'Видимость профиля'},
    'report.instagramFollowers':{en:'Instagram followers',tr:'Instagram takipçisi','zh-CN':'Instagram 粉丝',ru:'Подписчики Instagram'},
    'report.following':{en:'Following',tr:'Takip ettiği','zh-CN':'关注中',ru:'Подписки'},
    'report.threadsFollowers':{en:'Threads followers',tr:'Threads takipçisi','zh-CN':'Threads 粉丝',ru:'Подписчики Threads'},
    'report.highlightedStory':{en:'Highlights',tr:'Öne çıkan hikâye','zh-CN':'精选快拍',ru:'Актуальные истории'},
    'report.avatarUpdated':{en:'Profile photo updated',tr:'Profil fotoğrafı güncellendi','zh-CN':'头像更新时间',ru:'Фото профиля обновлено'},
    'report.approxRegion':{en:'Approximate network region',tr:'Yaklaşık ağ bölgesi','zh-CN':'大致网络区域',ru:'Примерный регион сети'},
    'report.regionCaveat':{en:'Estimated from language and network signals; this is not proof of real location.',tr:'Dil ve ağ işaretlerinden tahmin; gerçek konum kanıtı değildir.','zh-CN':'根据语言和网络信号估计；不能证明真实位置。',ru:'Оценка по языковым и сетевым сигналам; это не доказательство реального местоположения.'},
    'report.rawUnavailable':{en:'Technical text report is unavailable.',tr:'Teknik metin raporu bulunamadı.','zh-CN':'技术文本报告不可用。',ru:'Технический текстовый отчёт недоступен.'},

                                                                     
    'target.emptyTitle':{en:'Profile summary unavailable',tr:'Profil özeti bulunamadı','zh-CN':'无法获取资料摘要',ru:'Сводка профиля недоступна'},
    'target.emptyText':{en:'Run the analysis again for this target.',tr:'Bu hedef için analizi yeniden çalıştırın.','zh-CN':'请为此目标重新运行分析。',ru:'Повторно запустите анализ для этой цели.'},
    'target.analysisSignals':{en:'Analysis signals',tr:'Analiz sinyalleri','zh-CN':'分析信号',ru:'Сигналы анализа'},
    'target.inferenceCaveat':{en:'Inferred fields are data signals, not confirmed facts.',tr:'Çıkarıma dayalı alanlar kesin bilgi değil, veri işaretleridir.','zh-CN':'推断字段只是数据信号，并非已确认事实。',ru:'Поля, полученные выводом, — это сигналы данных, а не подтверждённые факты.'},
    'target.rareTechnical':{en:'Occasionally needed network and internal identifiers.',tr:'Nadiren gereken ağ ve iç kimlik bilgileri.','zh-CN':'偶尔需要的网络与内部标识符。',ru:'Сетевые и внутренние идентификаторы, которые требуются редко.'},
    'target.accountTypeText':{en:'Instagram’s account classification.',tr:'Instagram’ın hesap sınıflandırması.','zh-CN':'Instagram 的账户分类。',ru:'Классификация аккаунта Instagram.'},
    'target.businessAccount':{en:'Business account',tr:'İşletme hesabı','zh-CN':'企业账户',ru:'Бизнес-аккаунт'},
    'target.businessLabel':{en:'Business',tr:'İşletme','zh-CN':'企业',ru:'Бизнес'},
    'target.professionalAccount':{en:'Professional account',tr:'Profesyonel hesap','zh-CN':'专业账户',ru:'Профессиональный аккаунт'},
    'target.personalAccount':{en:'Personal account',tr:'Kişisel hesap','zh-CN':'个人账户',ru:'Личный аккаунт'},
    'target.creatorAccount':{en:'Creator account',tr:'İçerik üretici hesabı','zh-CN':'创作者账户',ru:'Аккаунт автора'},
    'target.accountTypeUnknown':{en:'Account type unknown',tr:'Hesap türü bilinmiyor','zh-CN':'账户类型未知',ru:'Тип аккаунта неизвестен'},
    'target.blueTickPresent':{en:'Verified badge present',tr:'Mavi tik var','zh-CN':'有认证标记',ru:'Есть отметка подтверждения'},
    'target.visibleEmail':{en:'Visible email',tr:'Görünür e-posta','zh-CN':'公开邮箱',ru:'Видимый адрес эл. почты'},
    'target.visiblePhone':{en:'Visible phone',tr:'Görünür telefon','zh-CN':'公开电话',ru:'Видимый телефон'},
    'target.profileAddress':{en:'Profile address',tr:'Profil adresi','zh-CN':'资料地址',ru:'Адрес в профиле'},
    'target.businessAddressNote':{en:'Information published as the business address on the profile.',tr:'Profilde işletme adresi olarak yayımlanan bilgi.','zh-CN':'资料中作为企业地址发布的信息。',ru:'Сведения, опубликованные в профиле как адрес компании.'},
    'target.profileLink':{en:'Profile link',tr:'Profil bağlantısı','zh-CN':'资料链接',ru:'Ссылка профиля'},
    'target.joinDate':{en:'Join date',tr:'Katılma tarihi','zh-CN':'加入日期',ru:'Дата регистрации'},
    'target.openedCountry':{en:'Country where opened',tr:'Açıldığı ülke','zh-CN':'注册国家/地区',ru:'Страна регистрации'},
    'target.notCurrentLocation':{en:'This does not indicate the current location.',tr:'Güncel konum anlamına gelmez.','zh-CN':'这不代表当前位置。',ru:'Это не указывает текущее местоположение.'},
    'target.accountAge':{en:'Account age',tr:'Hesap yaşı','zh-CN':'账户年龄',ru:'Возраст аккаунта'},
    'target.formerUsernames':{en:'Former usernames',tr:'Önceki kullanıcı adları','zh-CN':'曾用用户名',ru:'Прежние имена пользователя'},
    'target.nameChanges':{en:'Name changes',tr:'Ad değişikliği','zh-CN':'姓名更改',ru:'Изменения имени'},
    'target.ownershipChange':{en:'Ownership-change record',tr:'Sahiplik değişikliği kaydı','zh-CN':'所有权变更记录',ru:'Запись о смене владельца'},
    'target.ownershipCaveat':{en:'This value alone does not mean the account was compromised.',tr:'Bu değer tek başına hesap ele geçirilmesi demek değildir.','zh-CN':'仅凭此值不能说明账户被盗。',ru:'Само по себе это значение не означает взлом аккаунта.'},
    'target.adHistory':{en:'Advertising history',tr:'Reklam geçmişi','zh-CN':'广告历史',ru:'История рекламы'},
    'target.hasAdvertised':{en:'Has advertised',tr:'Reklam vermiş','zh-CN':'投放过广告',ru:'Размещал рекламу'},
    'target.politicalAds':{en:'Political advertising',tr:'Siyasi reklam','zh-CN':'政治广告',ru:'Политическая реклама'},
    'target.highlights':{en:'Highlights',tr:'Öne çıkanlar','zh-CN':'精选',ru:'Актуальное'},
    'target.lastStory':{en:'Last visible story',tr:'Son görülen hikâye','zh-CN':'最近可见快拍',ru:'Последняя видимая история'},
    'target.youFollow':{en:'You follow this account',tr:'Bu hesabı takip ediyorsunuz','zh-CN':'您关注了此账户',ru:'Вы подписаны на этот аккаунт'},
    'target.followsYou':{en:'This account follows you',tr:'Bu hesap sizi takip ediyor','zh-CN':'此账户关注了您',ru:'Этот аккаунт подписан на вас'},
    'target.incomingRequest':{en:'Follow request from this account',tr:'Bu hesaptan takip isteği','zh-CN':'来自此账户的关注请求',ru:'Запрос на подписку от этого аккаунта'},
    'target.outgoingRequest':{en:'Follow request sent to this account',tr:'Bu hesaba gönderilen istek','zh-CN':'已向此账户发送关注请求',ru:'Запрос, отправленный этому аккаунту'},
    'target.closeFriendsList':{en:'Close Friends list',tr:'Yakın arkadaşlar listesi','zh-CN':'密友列表',ru:'Список близких друзей'},
    'target.favoritesFeed':{en:'Favorites feed',tr:'Favoriler akışı','zh-CN':'收藏动态',ru:'Лента избранного'},
    'target.restricted':{en:'Restricted',tr:'Kısıtlanmış','zh-CN':'已限制',ru:'Ограничен'},
    'target.blocked':{en:'Blocked',tr:'Engellenmiş','zh-CN':'已屏蔽',ru:'Заблокирован'},
    'target.directMessage':{en:'Direct messages allowed',tr:'Doğrudan mesaj gönderilebilir','zh-CN':'可直接发送消息',ru:'Можно отправить прямое сообщение'},
    'target.messageRequest':{en:'Sent as a message request',tr:'Mesaj isteği olarak gider','zh-CN':'将作为消息请求发送',ru:'Будет отправлено как запрос на переписку'},
    'target.cannotMessage':{en:'Messaging unavailable',tr:'Mesaj gönderilemiyor','zh-CN':'无法发送消息',ru:'Нельзя отправить сообщение'},
    'target.messagingAction':{en:'Messaging',tr:'Mesaj gönderme','zh-CN':'消息发送',ru:'Отправка сообщений'},
    'target.existingConnection':{en:'Existing connection',tr:'Mevcut bağlantı','zh-CN':'现有关联',ru:'Существующая связь'},
    'target.connectionVisible':{en:'Connection visible',tr:'Bağlantı var','zh-CN':'有关联',ru:'Связь видна'},
    'target.connectionHidden':{en:'No visible connection',tr:'Bağlantı görünmüyor','zh-CN':'未见关联',ru:'Связь не видна'},
    'target.replyTendency':{en:'Reply tendency',tr:'Yanıt eğilimi','zh-CN':'回复倾向',ru:'Склонность отвечать'},
    'target.replyImmediate':{en:'Usually replies almost immediately',tr:'Genellikle hemen yanıtlıyor','zh-CN':'通常几乎立即回复',ru:'Обычно отвечает почти сразу'},
    'target.replyWithinHours':{en:'Usually replies within a few hours',tr:'Genellikle birkaç saat içinde yanıtlıyor','zh-CN':'通常在几小时内回复',ru:'Обычно отвечает в течение нескольких часов'},
    'target.replyWithinDay':{en:'Usually replies within a day',tr:'Genellikle bir gün içinde yanıtlıyor','zh-CN':'通常在一天内回复',ru:'Обычно отвечает в течение дня'},
    'target.replyWithinWeek':{en:'Usually replies within a week',tr:'Genellikle bir hafta içinde yanıtlıyor','zh-CN':'通常在一周内回复',ru:'Обычно отвечает в течение недели'},
    'target.replyFast':{en:'Usually replies quickly',tr:'Genellikle hızlı yanıtlıyor','zh-CN':'通常回复较快',ru:'Обычно отвечает быстро'},
    'target.replySlow':{en:'Usually takes longer to reply',tr:'Genellikle daha geç yanıtlıyor','zh-CN':'通常需要更长时间回复',ru:'Обычно отвечает не сразу'},
    'target.replyPatternAvailable':{en:'Instagram supplied a response-speed category',tr:'Instagram bir yanıt hızı kategorisi bildirdi','zh-CN':'Instagram 提供了回复速度类别',ru:'Instagram предоставил категорию скорости ответа'},
    'target.safetyWarning':{en:'Safety warning',tr:'Güvenlik uyarısı','zh-CN':'安全警告',ru:'Предупреждение безопасности'},
    'target.messageRequestLimit':{en:'Message-request limit',tr:'Mesaj isteği sınırı','zh-CN':'消息请求限制',ru:'Лимит запросов на переписку'},
    'target.limitReached':{en:'Limit reached',tr:'Sınıra ulaşılmış','zh-CN':'已达上限',ru:'Лимит достигнут'},
    'target.activeNow':{en:'Active now',tr:'Şu an aktif','zh-CN':'当前在线',ru:'Сейчас в сети'},
    'target.lastSeen':{en:'Last seen',tr:'Son görülme','zh-CN':'最后在线',ru:'Последняя активность'},
    'target.existingConversation':{en:'Existing conversation',tr:'Mevcut konuşma','zh-CN':'现有对话',ru:'Существующая переписка'},
    'target.lastConversation':{en:'Last conversation',tr:'Son konuşma','zh-CN':'最近对话',ru:'Последняя переписка'},
    'target.conversationMuted':{en:'Conversation muted',tr:'Konuşma sessizde','zh-CN':'对话已静音',ru:'Переписка без звука'},
    'target.notVisibleSession':{en:'Not visible in this session',tr:'Bu oturumda görünmüyor','zh-CN':'当前会话不可见',ru:'Не видно в этом сеансе'},
    'target.birthdayStateAvailable':{en:'Instagram supplied a birthday visibility state',tr:'Instagram bir doğum günü görünürlük durumu bildirdi','zh-CN':'Instagram 提供了生日可见性状态',ru:'Instagram предоставил статус видимости дня рождения'},
    'target.visibility':{en:'Visibility',tr:'Görünürlük','zh-CN':'可见性',ru:'Видимость'},
    'target.birthdaySignal':{en:'Birthday signal',tr:'Doğum günü işareti','zh-CN':'生日信号',ru:'Сигнал дня рождения'},
    'target.availableOnInstagram':{en:'Available on Instagram',tr:'Instagram’da mevcut','zh-CN':'Instagram 中有记录',ru:'Есть в Instagram'},
    'target.birthdayCaveat':{en:'This signal does not mean the full date of birth is known.',tr:'Bu işaret tam doğum tarihinin bilindiği anlamına gelmez.','zh-CN':'此信号不表示已知完整出生日期。',ru:'Этот сигнал не означает, что известна полная дата рождения.'},
    'target.isToday':{en:'Is it today?',tr:'Bugün mü?','zh-CN':'是今天吗？',ru:'Сегодня?'},
    'target.username':{en:'Username',tr:'Kullanıcı adı','zh-CN':'用户名',ru:'Имя пользователя'},
    'target.maskedEmail':{en:'Masked email',tr:'Maskeli e-posta','zh-CN':'脱敏邮箱',ru:'Скрытый адрес эл. почты'},
    'target.notFullAddress':{en:'This is not a full address.',tr:'Tam adres değildir.','zh-CN':'这不是完整地址。',ru:'Это не полный адрес.'},
    'target.maskedPhone':{en:'Masked phone',tr:'Maskeli telefon','zh-CN':'脱敏电话',ru:'Скрытый телефон'},
    'target.notFullNumber':{en:'This is not a full number.',tr:'Tam numara değildir.','zh-CN':'这不是完整号码。',ru:'Это не полный номер.'},
    'target.emailRecovery':{en:'Email recovery',tr:'E-posta ile kurtarma','zh-CN':'邮箱恢复',ru:'Восстановление по эл. почте'},
    'target.smsRecovery':{en:'SMS recovery',tr:'SMS ile kurtarma','zh-CN':'短信恢复',ru:'Восстановление по SMS'},
    'target.twoFactor':{en:'Two-factor authentication',tr:'İki adımlı doğrulama','zh-CN':'双重验证',ru:'Двухфакторная аутентификация'},
    'target.notRequired':{en:'Not required',tr:'Gerekli görünmüyor','zh-CN':'似乎不需要',ru:'По-видимому, не требуется'},
    'target.facebookConnection':{en:'Facebook connection',tr:'Facebook bağlantısı','zh-CN':'Facebook 关联',ru:'Связь с Facebook'},
    'target.requestStatus':{en:'Request status',tr:'İstek durumu','zh-CN':'请求状态',ru:'Статус запроса'},
    'target.temporarilyLimited':{en:'Temporarily limited by Instagram',tr:'Instagram geçici olarak sınırladı','zh-CN':'Instagram 暂时限制',ru:'Instagram временно ограничил'},
    'target.estimatedUpload':{en:'Estimated upload date',tr:'Tahmini yüklenme tarihi','zh-CN':'估计上传日期',ru:'Примерная дата загрузки'},
    'target.avatarTimestampNote':{en:'Derived from the timestamp in the profile-photo identifier.',tr:'Profil fotoğrafı kimliğindeki zaman bilgisinden çıkarılır.','zh-CN':'根据头像标识符中的时间信息推导。',ru:'Определяется по времени в идентификаторе фото профиля.'},
    'target.photoAge':{en:'Photo age',tr:'Fotoğraf yaşı','zh-CN':'照片时间',ru:'Возраст фотографии'},
    'target.accountMatch':{en:'Account match',tr:'Hesapla eşleşme','zh-CN':'账户匹配',ru:'Совпадение с аккаунтом'},
    'target.photoMatches':{en:'Photo identifier matches the account',tr:'Fotoğraf kimliği hesapla eşleşiyor','zh-CN':'照片标识符与账户匹配',ru:'Идентификатор фото совпадает с аккаунтом'},
    'target.noMatch':{en:'No match observed',tr:'Eşleşme görülmedi','zh-CN':'未发现匹配',ru:'Совпадение не обнаружено'},
    'target.otherAccountTrace':{en:'Other-account trace',tr:'Başka hesap izi','zh-CN':'其他账户痕迹',ru:'След другого аккаунта'},
    'target.otherAccountMatch':{en:'A different account identifier matched',tr:'Farklı hesap kimliğiyle eşleşme var','zh-CN':'匹配到不同的账户标识符',ru:'Есть совпадение с идентификатором другого аккаунта'},
    'target.photoCaveat':{en:'This is only a technical signal; it does not prove the photo was stolen.',tr:'Bu yalnız teknik bir işarettir; fotoğrafın çalındığını kanıtlamaz.','zh-CN':'这只是技术信号，不能证明照片被盗用。',ru:'Это лишь технический сигнал; он не доказывает кражу фотографии.'},
    'target.metaContentId':{en:'Meta content identifier',tr:'Meta içerik kimliği','zh-CN':'Meta 内容标识符',ru:'Идентификатор контента Meta'},
    'target.photoInternalId':{en:'The photo record’s internal number.',tr:'Fotoğraf kaydının dahili numarasıdır.','zh-CN':'照片记录的内部编号。',ru:'Внутренний номер записи фотографии.'},
    'target.encodedId':{en:'Encoded identifier',tr:'Kodlanmış kimlik','zh-CN':'编码标识符',ru:'Кодированный идентификатор'},
    'target.hexNote':{en:'The same number in hexadecimal form.',tr:'Aynı numaranın onaltılık gösterimidir.','zh-CN':'同一数字的十六进制表示。',ru:'То же число в шестнадцатеричном виде.'},
    'target.strong':{en:'Strong',tr:'Güçlü','zh-CN':'强',ru:'Высокая'},
    'target.locationUnknown':{en:'Location unclear',tr:'Konum belirsiz','zh-CN':'位置不明确',ru:'Местоположение неясно'},
    'target.countryTie':{en:'Several countries have equal weight.',tr:'Birden fazla ülke aynı güçte.','zh-CN':'多个国家/地区权重相同。',ru:'Несколько стран имеют одинаковый вес.'},
    'target.insufficientClues':{en:'Not enough signals.',tr:'Yeterli işaret yok.','zh-CN':'信号不足。',ru:'Недостаточно сигналов.'},
    'target.timeSample':{en:'Time sample',tr:'Zaman örneği','zh-CN':'时间样本',ru:'Временная выборка'},
    'target.smallSample':{en:'A small sample can make the result unreliable.',tr:'Az örnek, sonucu güvenilmez yapabilir.','zh-CN':'样本过少可能导致结果不可靠。',ru:'Малая выборка может сделать результат ненадёжным.'},
    'target.timezoneClue':{en:'Time-zone clue',tr:'Saat dilimi ipucu','zh-CN':'时区线索',ru:'Признак часового пояса'},
    'target.timezoneMethod':{en:'Estimated from activity times.',tr:'Etkinlik saatlerinden tahmin edilir.','zh-CN':'根据活动时间估计。',ru:'Оценивается по времени активности.'},
    'target.taggedLocation':{en:'Tagged location',tr:'Etiketli konum','zh-CN':'标记位置',ru:'Отмеченное место'},
    'target.notResidence':{en:'This does not indicate a home address.',tr:'İkamet adresi anlamına gelmez.','zh-CN':'这不代表居住地址。',ru:'Это не означает адрес проживания.'},
    'target.bioMatch':{en:'Biography match',tr:'Biyografi eşleşmesi','zh-CN':'简介匹配',ru:'Совпадение в описании'},
    'target.networkLanguage':{en:'Related-network language',tr:'İlişkili ağın dili','zh-CN':'关联网络语言',ru:'Язык связанной сети'},
    'target.turkishNetworkCaveat':{en:'A Turkish-speaking network does not prove that the target lives in Türkiye.',tr:'Türkçe konuşan bir ağ, hedefin Türkiye’de yaşadığını kanıtlamaz.','zh-CN':'土耳其语网络不能证明目标居住在土耳其。',ru:'Турецкоязычная сеть не доказывает, что цель живёт в Турции.'},
    'target.networkPhotoHours':{en:'Network photo times',tr:'Ağdaki fotoğraf saatleri','zh-CN':'网络头像时间',ru:'Время фотографий в сети'},
    'target.notTargetLocation':{en:'This is not the target’s own location.',tr:'Hedefin kendi konumu değildir.','zh-CN':'这不是目标本人的位置。',ru:'Это не местоположение самой цели.'},
    'target.unnamedLocation':{en:'Unnamed location',tr:'Adsız konum','zh-CN':'未命名位置',ru:'Место без названия'},
    'target.placeRecordCount':{en:'{place} · {count} records',tr:'{place} · {count} kayıt','zh-CN':'{place} · {count} 条记录',ru:'{place} · записей: {count}'},
    'target.cdnCaveat':{en:'The CDN region is the server that answered the request, not the target’s location.',tr:'CDN bölgesi isteği karşılayan sunucudur; hedefin konumu değildir.','zh-CN':'CDN 区域表示响应请求的服务器，并非目标位置。',ru:'Регион CDN — это сервер, ответивший на запрос, а не местоположение цели.'},
    'target.altFollowers':{en:'Followers (alternate source)',tr:'Takipçi (alternatif kaynak)','zh-CN':'粉丝（其他来源）',ru:'Подписчики (другой источник)'},
    'target.altSourceCaveat':{en:'This came from another Instagram response and may differ from the main count.',tr:'Başka bir Instagram yanıtından geldiği için ana sayıyla farklı olabilir.','zh-CN':'此数据来自另一条 Instagram 响应，可能与主要数量不同。',ru:'Это значение получено из другого ответа Instagram и может отличаться от основного.'},
    'target.taggedContent':{en:'Tagged content',tr:'Etiketlendiği içerik','zh-CN':'被标记内容',ru:'Отмеченный контент'},
    'target.reels':{en:'Reels / short videos',tr:'Reels / kısa video','zh-CN':'Reels / 短视频',ru:'Reels / короткие видео'},
    'target.longVideos':{en:'Long videos',tr:'Uzun video','zh-CN':'长视频',ru:'Длинные видео'},
    'target.friendSuggestions':{en:'Friend suggestions',tr:'Arkadaş önerileri','zh-CN':'好友推荐',ru:'Рекомендации друзей'},
    'target.appearsOn':{en:'Appears enabled',tr:'Açık görünüyor','zh-CN':'似乎已开启',ru:'Похоже, включено'},
    'target.appearsOff':{en:'Appears disabled',tr:'Kapalı görünüyor','zh-CN':'似乎已关闭',ru:'Похоже, выключено'},
    'target.gridViews':{en:'Grid view counts',tr:'Izgara görüntülenmeleri','zh-CN':'网格浏览量',ru:'Просмотры в сетке'},
    'target.canShow':{en:'Can be shown',tr:'Gösterilebilir','zh-CN':'可显示',ru:'Может отображаться'},
    'target.postInsights':{en:'Post insights',tr:'Gönderi istatistikleri','zh-CN':'帖子统计',ru:'Статистика публикаций'},
    'target.menuSignalPresent':{en:'Menu signal present',tr:'Menü işareti mevcut','zh-CN':'菜单信号存在',ru:'Признак меню есть'},
    'target.menuSignalAbsent':{en:'No menu signal',tr:'Menü işareti yok','zh-CN':'无菜单信号',ru:'Признака меню нет'},
    'target.taggedTab':{en:'Tagged tab',tr:'Etiketlenenler sekmesi','zh-CN':'被标记标签页',ru:'Вкладка отметок'},
    'target.threadsTab':{en:'Threads tab on profile',tr:'Profilde Threads sekmesi','zh-CN':'资料中的 Threads 标签页',ru:'Вкладка Threads в профиле'},
    'target.transparency':{en:'Account transparency',tr:'Hesap şeffaflığı','zh-CN':'账户透明度',ru:'Прозрачность аккаунта'},
    'target.sectionPresent':{en:'Section available',tr:'Bölüm mevcut','zh-CN':'板块可用',ru:'Раздел доступен'},
    'target.sectionAbsent':{en:'Section not visible',tr:'Bölüm görünmüyor','zh-CN':'板块不可见',ru:'Раздел не виден'},
    'target.messageFiltering':{en:'Message-filtering information',tr:'Mesaj filtreleme bilgisi','zh-CN':'消息过滤信息',ru:'Сведения о фильтрации сообщений'},
    'target.infoFound':{en:'Information found',tr:'Bilgi görüldü','zh-CN':'发现信息',ru:'Сведения найдены'},
    'target.metaVerified':{en:'Meta Verified subscription',tr:'Meta Verified aboneliği','zh-CN':'Meta Verified 订阅',ru:'Подписка Meta Verified'},
    'target.metaEligible':{en:'Meta Verified eligibility',tr:'Meta Verified uygunluğu','zh-CN':'Meta Verified 资格',ru:'Доступность Meta Verified'},
    'target.subscriptionOffer':{en:'Subscription offer',tr:'Abonelik teklifi','zh-CN':'订阅优惠',ru:'Предложение подписки'},
    'target.activeFundraiser':{en:'Active fundraiser',tr:'Aktif bağış kampanyası','zh-CN':'进行中的筹款活动',ru:'Активный сбор средств'},
    'target.currentObsession':{en:'My current obsession',tr:'Şu anki ilgim','zh-CN':'我目前最感兴趣的',ru:'Моё текущее увлечение'},
    'target.dreamDestination':{en:'My dream destination',tr:'Hayalimdeki yer','zh-CN':'我的梦想目的地',ru:'Место моей мечты'},
    'target.playing':{en:'Playing',tr:'Oynadığım','zh-CN':'正在玩',ru:'Играю'},
    'target.reading':{en:'Reading',tr:'Okuduğum','zh-CN':'正在读',ru:'Читаю'},
    'target.watching':{en:'Watching',tr:'İzlediğim','zh-CN':'正在看',ru:'Смотрю'},
    'target.seekingRecommendations':{en:'Looking for recommendations',tr:'Öneri arıyorum','zh-CN':'征求推荐',ru:'Ищу рекомендации'},
    'target.promptTemplate':{en:'Prompt template',tr:'Soru şablonu','zh-CN':'问题模板',ru:'Шаблон вопроса'},
    'target.instagramId':{en:'Instagram account identifier',tr:'Instagram hesap kimliği','zh-CN':'Instagram 账户标识符',ru:'Идентификатор аккаунта Instagram'},
    'target.instagramIdNote':{en:'Instagram’s internal number for the account.',tr:'Instagram’ın hesaba verdiği dahili numara.','zh-CN':'Instagram 为账户分配的内部编号。',ru:'Внутренний номер аккаунта в Instagram.'},
    'target.metaProfileId':{en:'Meta profile identifier',tr:'Meta profil kimliği','zh-CN':'Meta 资料标识符',ru:'Идентификатор профиля Meta'},
    'target.notPublicFacebookId':{en:'This is not a public Facebook profile number.',tr:'Herkese açık Facebook profil numarası değildir.','zh-CN':'这不是公开的 Facebook 资料编号。',ru:'Это не публичный номер профиля Facebook.'},
    'target.messagingId':{en:'Messaging identifier',tr:'Mesajlaşma kimliği','zh-CN':'消息标识符',ru:'Идентификатор сообщений'},
    'target.messagingIdNote':{en:'An internal messaging number used across Meta applications.',tr:'Meta uygulamaları arasındaki dahili mesajlaşma numarası.','zh-CN':'Meta 应用间使用的内部消息编号。',ru:'Внутренний номер для сообщений между приложениями Meta.'},
    'target.unifiedMetaId':{en:'Unified Meta identifier',tr:'Birleşik Meta kimliği','zh-CN':'统一 Meta 标识符',ru:'Единый идентификатор Meta'},
    'target.unifiedMetaIdNote':{en:'An internal cross-platform matching key.',tr:'Platformlar arası dahili eşleştirme anahtarı.','zh-CN':'跨平台内部匹配键。',ru:'Внутренний ключ сопоставления между платформами.'},
    'target.cdnServer':{en:'Responding CDN',tr:'İsteği karşılayan CDN','zh-CN':'响应请求的 CDN',ru:'Ответивший CDN'},
    'target.cdnNotLocation':{en:'This is the Meta server reached by the request, not the target’s location.',tr:'Hedefin konumu değil, isteğin ulaştığı Meta sunucusudur.','zh-CN':'这是请求到达的 Meta 服务器，并非目标位置。',ru:'Это сервер Meta, до которого дошёл запрос, а не местоположение цели.'},
    'target.photoLinkExpiry':{en:'Photo-link expiry',tr:'Fotoğraf bağlantısı geçerliliği','zh-CN':'照片链接有效期',ru:'Срок действия ссылки на фото'},
    'target.diagnosticHeader':{en:'Response diagnostic header',tr:'Yanıt tanılama başlığı','zh-CN':'响应诊断标头',ru:'Диагностический заголовок ответа'},
    'target.debugOnly':{en:'Used for debugging; this is not personal information.',tr:'Hata ayıklama içindir; kişi bilgisi değildir.','zh-CN':'仅用于调试，并非个人信息。',ru:'Используется для отладки; это не личные сведения.'},
    'target.youFollowing':{en:'Test account follows',tr:'Test hesabının takip ettiği','zh-CN':'测试账户关注',ru:'Тестовый аккаунт подписан'},
    'target.followsYouCount':{en:'Follows test account',tr:'Test hesabını takip eden','zh-CN':'关注测试账户',ru:'Подписаны на тестовый аккаунт'},
    'target.requestSent':{en:'Requested the test account',tr:'Test hesabına istek gönderdi','zh-CN':'已向测试账户发送请求',ru:'Отправил запрос тестовому аккаунту'},
    'target.youSentRequest':{en:'Test account requested',tr:'Test hesabı istek gönderdi','zh-CN':'测试账户已发送请求',ru:'Тестовый аккаунт отправил запрос'},
    'target.otherStatuses':{en:'Other statuses',tr:'Diğer durumlar','zh-CN':'其他状态',ru:'Другие статусы'},
    'target.notFoundShort':{en:'Not found',tr:'Bulunmadı','zh-CN':'未找到',ru:'Не найдено'},
    'target.post':{en:'Posts',tr:'Gönderi','zh-CN':'帖子',ru:'Публикации'},
    'target.highlight':{en:'Highlights',tr:'Öne çıkan','zh-CN':'精选',ru:'Актуальное'},
    'target.restrictedShort':{en:'Restricted',tr:'Kısıtlı','zh-CN':'受限',ru:'Ограничен'},
    'target.viewerLanguageCaveat':{en:'The page language belongs to this session or browser; it does not indicate the target’s country.',tr:'Sayfa dili oturuma/tarayıcıya aittir; hedefin ülkesini göstermez.','zh-CN':'页面语言取决于当前会话或浏览器，不能说明目标所在国家/地区。',ru:'Язык страницы относится к сеансу или браузеру и не указывает страну цели.'},

                                                      
    'log.phase26Title':{en:'Checking profile and access information',tr:'Profil ve erişim bilgileri inceleniyor','zh-CN':'正在检查资料与访问信息',ru:'Проверяются профиль и доступ'},
    'log.phase26Text':{en:'Checking follow, messaging, and profile visibility.',tr:'Takip, mesajlaşma ve profil görünürlüğü kontrol ediliyor.','zh-CN':'正在检查关注、消息和资料可见性。',ru:'Проверяются подписки, сообщения и видимость профиля.'},
    'log.phase27Title':{en:'Checking account history',tr:'Hesap geçmişi kontrol ediliyor','zh-CN':'正在检查账户历史',ru:'Проверяется история аккаунта'},
    'log.phase27Text':{en:'Looking for account creation and transparency information.',tr:'Hesabın açılış ve şeffaflık bilgileri aranıyor.','zh-CN':'正在查找账户创建和透明度信息。',ru:'Ищутся сведения о регистрации и прозрачности аккаунта.'},
    'log.phase28Title':{en:'Scanning profile fields',tr:'Profil alanları taranıyor','zh-CN':'正在扫描资料字段',ru:'Сканируются поля профиля'},
    'log.phase28Text':{en:'Checking additional profile information provided by Instagram.',tr:'Instagram’ın sunduğu ek profil bilgileri kontrol ediliyor.','zh-CN':'正在检查 Instagram 提供的其他资料信息。',ru:'Проверяются дополнительные данные профиля от Instagram.'},
    'log.phase29Title':{en:'Checking past activity traces',tr:'Eski etkinlik izleri inceleniyor','zh-CN':'正在检查历史活动痕迹',ru:'Проверяются следы прежней активности'},
    'log.phase29Text':{en:'Looking for accessible past-activity signals.',tr:'Erişilebilen geçmiş etkinlik işaretleri aranıyor.','zh-CN':'正在查找可访问的历史活动信号。',ru:'Ищутся доступные сигналы прошлой активности.'},
    'log.phase30Title':{en:'Checking tagged content',tr:'Etiketli içerikler inceleniyor','zh-CN':'正在检查被标记内容',ru:'Проверяется отмеченный контент'},
    'log.phase30Text':{en:'Checking accessible content in which the profile was tagged.',tr:'Profilin etiketlendiği erişilebilir içerikler kontrol ediliyor.','zh-CN':'正在检查标记了该资料的可访问内容。',ru:'Проверяется доступный контент, в котором отмечен профиль.'},
    'log.phase31Title':{en:'Checking inbox signals',tr:'Mesaj kutusu işaretleri inceleniyor','zh-CN':'正在检查收件箱信号',ru:'Проверяются сигналы входящих'},
    'log.phase31Text':{en:'Looking for links visible to your signed-in account.',tr:'Giriş yaptığınız hesaba göre görülebilen bağlantılar aranıyor.','zh-CN':'正在查找当前登录账户可见的关联。',ru:'Ищутся связи, видимые аккаунту, под которым выполнен вход.'},
    'log.phase32Title':{en:'Collecting connection candidates',tr:'Bağlantı adayları toplanıyor','zh-CN':'正在收集关联候选',ru:'Собираются кандидаты связей'},
    'log.phase32Text':{en:'Merging the related-account network.',tr:'İlişkili hesap ağı birleştiriliyor.','zh-CN':'正在合并关联账户网络。',ru:'Объединяется сеть связанных аккаунтов.'},
    'log.phase33Title':{en:'Checking account details',tr:'Hesap ayrıntıları kontrol ediliyor','zh-CN':'正在检查账户详情',ru:'Проверяются сведения аккаунта'},
    'log.phase33Text':{en:'Organizing information found for the target profile.',tr:'Hedef profil için bulunan bilgiler düzenleniyor.','zh-CN':'正在整理为目标资料找到的信息。',ru:'Упорядочиваются сведения, найденные для целевого профиля.'},
    'log.phase34Title':{en:'Checking the follow network',tr:'Takip ağı inceleniyor','zh-CN':'正在检查关注网络',ru:'Проверяется сеть подписок'},
    'log.phase34Text':{en:'Comparing accessible follow connections.',tr:'Erişilebilen takip bağlantıları karşılaştırılıyor.','zh-CN':'正在比较可访问的关注关联。',ru:'Сравниваются доступные связи подписок.'},
    'log.phase35Title':{en:'Checking reciprocal recommendation overlap',tr:'Karşılıklı öneri örtüşmesi inceleniyor','zh-CN':'正在检查双向推荐重合',ru:'Проверяется взаимное пересечение рекомендаций'},
    'log.phase35Text':{en:'Comparing candidates seen in both directions of the recommendation chain; this does not prove a follow.',tr:'Öneri zincirinin iki yönünde görülen adaylar karşılaştırılıyor; bu takip kanıtı değildir.','zh-CN':'正在比较推荐链两个方向均出现的候选；这不能证明关注关系。',ru:'Сравниваются кандидаты, видимые в обоих направлениях цепочки рекомендаций; это не доказывает подписку.'},
    'log.phase37Title':{en:'Checking interaction proximity',tr:'Etkileşim yakınlığı kontrol ediliyor','zh-CN':'正在检查互动接近度',ru:'Проверяется близость взаимодействий'},
    'log.phase37Text':{en:'Evaluating share suggestions relative to your signed-in account.',tr:'Paylaşım önerileri giriş yaptığınız hesaba göre değerlendiriliyor.','zh-CN':'正在根据当前登录账户评估分享推荐。',ru:'Рекомендации отправки оцениваются относительно вашего аккаунта.'},
    'log.collectingFor':{en:'Collecting data for {username}.',tr:'{username} için veriler toplanıyor.','zh-CN':'正在收集 {username} 的数据。',ru:'Собираются данные для {username}.'},
    'log.collectorStarted':{en:'The local collection process started.',tr:'Yerel veri toplama işlemi başladı.','zh-CN':'本地采集进程已启动。',ru:'Локальный процесс сбора запущен.'},
    'log.depthWarning':{en:'A higher value checks more accounts and may trigger a request limit.',tr:'Daha yüksek değer daha fazla hesap kontrol eder ve istek sınırını tetikleyebilir.','zh-CN':'数值越高，检查的账户越多，也可能触发请求限制。',ru:'Большее значение проверяет больше аккаунтов и может вызвать лимит запросов.'},
    'log.sessionChecking':{en:'Instagram access is now being checked.',tr:'Instagram erişimi şimdi kontrol ediliyor.','zh-CN':'正在检查 Instagram 访问权限。',ru:'Сейчас проверяется доступ к Instagram.'},
    'log.allowedChecks':{en:'Permitted profile checks are running.',tr:'İzin verilen profil kontrolleri çalıştırılıyor.','zh-CN':'正在运行允许的资料检查。',ru:'Выполняются разрешённые проверки профиля.'},
    'log.followChecked':{en:'Follow connection checked',tr:'Takip bağlantısı kontrol edildi','zh-CN':'已检查关注关联',ru:'Связь подписки проверена'},
    'log.signedInPerspective':{en:'The result is shown from the perspective of your signed-in Instagram account.',tr:'Sonuç, giriş yaptığınız Instagram hesabına göre gösterilir.','zh-CN':'结果以当前登录的 Instagram 账户为视角显示。',ru:'Результат показан относительно аккаунта Instagram, под которым выполнен вход.'},
    'log.technicalSummarized':{en:'Technical fields will be summarized with clear labels on the results screen.',tr:'Teknik alanlar sonuç ekranında anlaşılır başlıklarla özetlenecek.','zh-CN':'技术字段将在结果页中以清晰标题汇总。',ru:'Технические поля будут изложены понятными пунктами на экране результатов.'},
    'log.birthdayChecked':{en:'Birthday visibility checked',tr:'Doğum günü görünürlüğü kontrol edildi','zh-CN':'已检查生日可见性',ru:'Видимость дня рождения проверена'},
    'log.birthdayLimit':{en:'This check does not reveal an exact date of birth.',tr:'Bu kontrol kesin doğum tarihi vermez.','zh-CN':'此检查不会提供准确出生日期。',ru:'Эта проверка не сообщает точную дату рождения.'},
    'log.avatarTimestamp':{en:'Profile-photo timing information found',tr:'Profil fotoğrafı zaman bilgisi alındı','zh-CN':'已获取头像时间信息',ru:'Получены сведения о времени фото профиля'},
    'log.avatarAge':{en:'The photo may have been updated about {count} days ago.',tr:'Fotoğraf yaklaşık {count} gün önce güncellenmiş olabilir.','zh-CN':'头像可能约在 {count} 天前更新。',ru:'Возможно, фото обновлено около {count} дн. назад.'},
    'log.avatarChecked':{en:'Profile photo checked',tr:'Profil fotoğrafı kontrol edildi','zh-CN':'已检查头像',ru:'Фото профиля проверено'},
    'log.avatarCheckedText':{en:'The photo’s technical time and account signals were reviewed.',tr:'Fotoğrafın teknik zaman ve hesap işaretleri incelendi.','zh-CN':'已检查照片的技术时间与账户信号。',ru:'Проверены техническое время фотографии и сигналы аккаунта.'},
    'log.storiesChecking':{en:'Checking stories and highlights',tr:'Hikâye ve öne çıkanlar kontrol ediliyor','zh-CN':'正在检查快拍与精选',ru:'Проверяются истории и актуальное'},
    'log.sessionVisibleOnly':{en:'Only information accessible in this session is being checked.',tr:'Yalnızca bu oturumda erişilebilen bilgiler aranıyor.','zh-CN':'仅查找当前会话可访问的信息。',ru:'Ищутся только сведения, доступные в этом сеансе.'},
    'log.noActiveStory':{en:'No active story information was available',tr:'Aktif hikâye bilgisi alınamadı','zh-CN':'无法获取当前快拍信息',ru:'Нет сведений об активных историях'},
    'log.storyLimitText':{en:'The profile may be private, have no active story, or access may be limited.',tr:'Profil gizli olabilir, aktif hikâye olmayabilir veya erişim sınırlı olabilir.','zh-CN':'资料可能为私密、没有当前快拍，或访问受限。',ru:'Профиль может быть закрыт, активных историй может не быть, либо доступ ограничен.'},
    'log.longChecksSkipped':{en:'Long checks skipped',tr:'Uzun kontroller atlandı','zh-CN':'已跳过耗时检查',ru:'Длительные проверки пропущены'},
    'log.fastSavesTime':{en:'Fast mode reduces unnecessary waiting.',tr:'Hızlı mod gereksiz beklemeyi azaltıyor.','zh-CN':'快速模式可减少不必要的等待。',ru:'Быстрый режим сокращает лишнее ожидание.'},
    'log.publicPageLimited':{en:'Public profile page returned a limited response',tr:'Genel profil sayfası sınırlı yanıt verdi','zh-CN':'公开资料页返回了受限响应',ru:'Публичная страница профиля вернула ограниченный ответ'},
    'log.loginWallText':{en:'Instagram returned a login page; accessible basic information was preserved.',tr:'Instagram giriş ekranı döndürdü; erişilebilen temel bilgiler korunuyor.','zh-CN':'Instagram 返回了登录页；已保留可访问的基本信息。',ru:'Instagram вернул страницу входа; доступные основные сведения сохранены.'},
    'log.uniqueFound':{en:'{count} unique accounts found so far.',tr:'Şimdiye kadar {count} benzersiz hesap bulundu.','zh-CN':'目前已找到 {count} 个唯一账户。',ru:'К этому моменту найдено уникальных аккаунтов: {count}.'},
    'log.duplicatesMerged':{en:'Repeated accounts were merged.',tr:'Tekrarlanan hesaplar birleştirildi.','zh-CN':'重复账户已合并。',ru:'Повторяющиеся аккаунты объединены.'},
    'log.mutualCaveat':{en:'Candidates appeared in both directions of the recommendation chain; this does not prove a follow or friendship.',tr:'Adaylar öneri zincirinin iki yönünde görüldü; bu takip veya arkadaşlık kanıtı değildir.','zh-CN':'候选在推荐链的两个方向均出现；这不能证明关注或好友关系。',ru:'Кандидаты появились в обоих направлениях цепочки рекомендаций; это не доказывает подписку или дружбу.'},
    'log.shareFound':{en:'Target signal found in share ranking',tr:'Paylaşım sıralamasında hedef işareti bulundu','zh-CN':'在分享排序中找到目标信号',ru:'Сигнал цели найден в рейтинге отправки'},
    'log.sharePerspective':{en:'The result reflects only the suggestion order for your signed-in account.',tr:'Sonuç yalnız giriş yaptığınız hesabın öneri sırasına göredir.','zh-CN':'结果仅反映当前登录账户的推荐顺序。',ru:'Результат отражает только порядок рекомендаций вашего аккаунта.'},
    'log.shareMissing':{en:'Target not seen in share ranking',tr:'Paylaşım sıralamasında hedef görünmedi','zh-CN':'分享排序中未出现目标',ru:'Цель не появилась в рейтинге отправки'},
    'log.noConnectionConclusion':{en:'This does not mean there is no connection.',tr:'Bu sonuç bağlantı olmadığı anlamına gelmez.','zh-CN':'这不表示不存在关联。',ru:'Это не означает, что связи нет.'},
    'log.refreshSession':{en:'Refresh the session information and try again.',tr:'Oturum bilgilerini yenileyip yeniden deneyin.','zh-CN':'请刷新会话信息后重试。',ru:'Обновите данные сеанса и повторите попытку.'},
    'log.retryLater':{en:'Try the analysis again later.',tr:'Analizi bir süre sonra yeniden deneyebilirsiniz.','zh-CN':'请稍后重新运行分析。',ru:'Повторите анализ позднее.'},
    'log.scoringNext':{en:'Found accounts are now being evaluated with uncalibrated model-confidence scores.',tr:'Bulunan hesaplar şimdi kalibre edilmemiş model güveni skorlarıyla değerlendiriliyor.','zh-CN':'正在使用未经校准的模型置信度分数评估找到的账户。',ru:'Найденные аккаунты оцениваются по некалиброванным оценкам уверенности модели.'},
    'log.inspectTechnical':{en:'Check the technical details for the cause.',tr:'Teknik ayrıntılardan hata nedenini kontrol edebilirsiniz.','zh-CN':'可在技术详情中查看原因。',ru:'Причину можно посмотреть в технических деталях.'},
    'log.groupedSignals':{en:'Found people were grouped by signal strength.',tr:'Bulunan kişiler sinyal güçlerine göre gruplandı.','zh-CN':'找到的人员已按信号强度分组。',ru:'Найденные люди сгруппированы по силе сигналов.'},
    'log.scoringSkipped':{en:'Scoring could not run',tr:'Skorlama çalıştırılamadı','zh-CN':'无法运行评分',ru:'Не удалось запустить оценку'},
    'log.previousStepFailed':{en:'The previous data-collection step did not finish.',tr:'Önceki veri toplama adımı tamamlanmadı.','zh-CN':'上一步数据收集未完成。',ru:'Предыдущий этап сбора данных не завершён.'},
    'log.refreshPageText':{en:'Refresh the page once to open the latest result.',tr:'Sayfayı bir kez yenileyerek güncel sonucu açabilirsiniz.','zh-CN':'刷新页面即可打开最新结果。',ru:'Обновите страницу, чтобы открыть актуальный результат.'},
    'log.incompleteDiscarded':{en:'Incomplete results were not applied to the interface.',tr:'Tamamlanmayan sonuçlar ekrana uygulanmadı.','zh-CN':'未完成的结果未应用到界面。',ru:'Незавершённые результаты не применены к интерфейсу.'},
    'log.retryWhileOpen':{en:'Try the analysis again while the application is open.',tr:'Uygulama açıkken analizi yeniden deneyin.','zh-CN':'请在应用保持打开时重试分析。',ru:'Повторите анализ, пока приложение открыто.'},
    'log.rawReasonStored':{en:'The detailed cause was kept in the technical log.',tr:'Ayrıntılı neden teknik kayıtta tutuldu.','zh-CN':'详细原因已保存在技术日志中。',ru:'Подробная причина сохранена в техническом журнале.'},
    'log.resultsLoadedFor':{en:'New results for {username} were loaded.',tr:'{username} için yeni sonuçlar ekrana yüklendi.','zh-CN':'已加载 {username} 的新结果。',ru:'Новые результаты для {username} загружены.'},

                                  
    'flag.veryHigh':{en:'Very high model confidence',tr:'Çok yüksek model güveni','zh-CN':'模型置信度极高',ru:'Очень высокая уверенность модели'},
    'flag.high':{en:'High model confidence',tr:'Yüksek model güveni','zh-CN':'高模型置信度',ru:'Высокая уверенность модели'},
    'flag.medium':{en:'Medium model confidence',tr:'Orta model güveni','zh-CN':'中等模型置信度',ru:'Средняя уверенность модели'},
    'flag.low':{en:'Low model confidence',tr:'Düşük model güveni','zh-CN':'低模型置信度',ru:'Низкая уверенность модели'},
    'flag.insufficient':{en:'Insufficient connection signal',tr:'Yetersiz bağlantı sinyali','zh-CN':'关联信号不足',ru:'Недостаточно сигналов связи'},
    'flag.unknown':{en:'No valid model score',tr:'Geçerli model skoru yok','zh-CN':'无有效模型分数',ru:'Нет действительной оценки модели'},
    'flag.mutual':{en:'Reciprocal recommendation overlap',tr:'Karşılıklı öneri örtüşmesi','zh-CN':'双向推荐重合',ru:'Взаимное пересечение рекомендаций'},
    'flag.oneWay':{en:'One-way recommendation-chain overlap',tr:'Tek yönlü öneri zinciri örtüşmesi','zh-CN':'单向推荐链重合',ru:'Одностороннее пересечение цепочки рекомендаций'},
    'flag.shareSeen':{en:'Seen {count} times in share suggestions',tr:'Paylaşım önerilerinde {count} kez görüldü','zh-CN':'在分享推荐中出现 {count} 次',ru:'Появился в рекомендациях отправки {count} раз'},
    'flag.shareSuggestions':{en:'Seen {count} times in sharing suggestions',tr:'Paylaşım önerilerinde {count} kez görüldü','zh-CN':'在分享推荐中出现 {count} 次',ru:'Появился в рекомендациях отправки {count} раз'},
    'detail.likesFound':{en:'{count} like records found.',tr:'{count} beğeni kaydı bulundu.','zh-CN':'发现 {count} 条点赞记录。',ru:'Найдено записей о лайках: {count}.'},
    'detail.commentsFound':{en:'{count} comment records found.',tr:'{count} yorum kaydı bulundu.','zh-CN':'发现 {count} 条评论记录。',ru:'Найдено записей о комментариях: {count}.'},
    'detail.tagsFound':{en:'{count} tagged items found.',tr:'{count} etiketli içerik bulundu.','zh-CN':'发现 {count} 条被标记内容。',ru:'Найдено отмеченных материалов: {count}.'},
    'detail.coTagsFound':{en:'{count} co-tagged items found.',tr:'{count} ortak etiketli içerik bulundu.','zh-CN':'发现 {count} 条共同标记内容。',ru:'Найдено совместно отмеченных материалов: {count}.'},
    'detail.interactionsFound':{en:'{count} interaction records found.',tr:'{count} etkileşim kaydı bulundu.','zh-CN':'发现 {count} 条互动记录。',ru:'Найдено записей взаимодействий: {count}.'},
    'detail.mutualFollowersFound':{en:'{count} followers shared with the signed-in test account.','tr':'Giriş yapılan test hesabıyla {count} ortak takipçi bulundu.','zh-CN':'发现与已登录测试账户共同的 {count} 个粉丝。',ru:'Общих подписчиков с тестовым аккаунтом: {count}.'},
    'detail.shareRankingCount':{en:'Seen {count} times in sharing rankings.',tr:'Paylaşım sıralamasında {count} kez görüldü.','zh-CN':'在分享排序中出现 {count} 次。',ru:'Появился в рейтинге отправки {count} раз.'},
    'detail.points':{en:'{value} points',tr:'{value} puan','zh-CN':'{value} 分',ru:'{value} баллов'},
    'target.geoWeakCandidate':{en:'Strongest candidate: {country}, but the signal is weak.',tr:'En güçlü aday: {country}, ancak sinyal zayıf.','zh-CN':'最强候选：{country}，但信号较弱。',ru:'Наиболее вероятный вариант: {country}, но сигнал слабый.'},
    'target.geoLead':{en:'Strongest candidate: {country}.',tr:'En güçlü aday: {country}.','zh-CN':'最强候选：{country}。',ru:'Наиболее вероятный вариант: {country}.'},
    'target.distinctPlaces':{en:'{count} distinct places',tr:'{count} farklı yer','zh-CN':'{count} 个不同地点',ru:'Разных мест: {count}'},
    'target.textClues':{en:'{count} text clues',tr:'{count} metin ipucu','zh-CN':'{count} 条文本线索',ru:'Текстовых признаков: {count}'},
    'target.turkishAccounts':{en:'{found} / {total} accounts show Turkish-language clues',tr:'{found} / {total} hesapta Türkçe dil işareti var','zh-CN':'{found} / {total} 个账户显示土耳其语线索',ru:'Турецкоязычные признаки у {found} из {total} аккаунтов'},
    'target.decodedOf':{en:'{found} / {total} decoded',tr:'{found} / {total} çözüldü','zh-CN':'已解析 {found} / {total}',ru:'Расшифровано {found} из {total}'},
    'target.decodedHours':{en:'{count} time records decoded',tr:'{count} saat kaydı çözüldü','zh-CN':'已解析 {count} 条时间记录',ru:'Расшифровано записей времени: {count}'},
    'target.confidenceValue':{en:'{confidence} confidence',tr:'{confidence} güven','zh-CN':'置信度：{confidence}','ru':'Уверенность: {confidence}'},
    'target.hourChartAria':{en:'24-hour distribution',tr:'24 saatlik dağılım','zh-CN':'24 小时分布',ru:'Распределение по 24 часам'},
    'target.hourRecordTitle':{en:'UTC {hour}:00 · {count} records',tr:'UTC {hour}:00 · {count} kayıt','zh-CN':'UTC {hour}:00 · {count} 条记录',ru:'UTC {hour}:00 · записей: {count}'},
    'target.approxDays':{en:'About {count} days',tr:'Yaklaşık {count} gün','zh-CN':'约 {count} 天',ru:'Около {count} дн.'},
    'target.paidSubscribers':{en:'{count} paid subscribers',tr:'{count} ücretli abone','zh-CN':'{count} 名付费订阅者',ru:'Платных подписчиков: {count}'},
    'target.facebookCandidatesFor':{en:'Links found for {username} are only candidates, not verified identity matches.',tr:'{username} için bulunan bağlantılar yalnızca adaydır; doğrulanmış kimlik eşleşmesi değildir.','zh-CN':'为 {username} 找到的链接只是候选，并非已验证的身份匹配。',ru:'Ссылки, найденные для {username}, — лишь кандидаты, а не подтверждённые совпадения личности.'},
    'target.moreAccounts':{en:'First 60 accounts shown; {count} more.',tr:'İlk 60 hesap gösteriliyor; {count} hesap daha var.','zh-CN':'显示前 60 个账户；另有 {count} 个。',ru:'Показаны первые 60 аккаунтов; ещё {count}.'},
    'reportSignal.nearTarget':{en:'Around the target',tr:'Hedef çevresinde','zh-CN':'目标周边',ru:'Вокруг цели'},
    'reportSignal.nearTargetText':{en:'Appeared in account suggestions around the target.',tr:'Hedefin çevresindeki hesap önerilerinde görüldü.','zh-CN':'出现在目标周边的账户推荐中。',ru:'Появился в рекомендациях аккаунтов вокруг цели.'},
    'reportSignal.repeated':{en:'Repeated match',tr:'Tekrarlı eşleşme','zh-CN':'重复匹配',ru:'Повторное совпадение'},
    'reportSignal.repeatedText':{en:'Appeared again across several analysis areas.',tr:'Birden fazla analiz alanında tekrar görüldü.','zh-CN':'在多个分析区域中重复出现。',ru:'Повторно появился в нескольких областях анализа.'},
    'reportSignal.networkScan':{en:'Network scan',tr:'Ağ taraması','zh-CN':'网络扫描',ru:'Сканирование сети'},
    'reportSignal.networkScanText':{en:'Appeared in repeated network scans.',tr:'Tekrarlanan ağ taramalarında görünür oldu.','zh-CN':'出现在多次网络扫描中。',ru:'Появился в повторных сканированиях сети.'},
    'reportSignal.generalText':{en:'Appeared in general Instagram suggestions.',tr:'Instagram genel önerilerinde görüldü.','zh-CN':'出现在 Instagram 普通推荐中。',ru:'Появился в общих рекомендациях Instagram.'},
    'reportSignal.suggestionMatch':{en:'Suggestion match',tr:'Öneri eşleşmesi','zh-CN':'推荐匹配',ru:'Совпадение в рекомендациях'},
    'reportSignal.suggestionMatchText':{en:'Appeared in people suggestions for the signed-in session.',tr:'Giriş yapılan oturumun kişi önerilerinde görüldü.','zh-CN':'出现在当前登录会话的人员推荐中。',ru:'Появился в рекомендациях людей для текущего сеанса.'},
    'reportSignal.reciprocalTrace':{en:'Reciprocal recommendation overlap',tr:'Karşılıklı öneri örtüşmesi','zh-CN':'双向推荐重合',ru:'Взаимное пересечение рекомендаций'},
    'reportSignal.reciprocalTraceText':{en:'A two-way match appeared in the recommendation chain around the target; this does not prove a follow.',tr:'Hedef çevresindeki öneri zincirinde iki yönlü eşleşme görüldü; bu takip kanıtı değildir.','zh-CN':'目标周边的推荐链中出现双向匹配；这不能证明关注关系。',ru:'В цепочке рекомендаций вокруг цели найдено двустороннее совпадение; это не доказывает подписку.'},
    'reportSignal.like':{en:'Like signal',tr:'Beğeni işareti','zh-CN':'点赞信号',ru:'Сигнал лайков'},
    'reportSignal.likeText':{en:'Like interaction was found in content.',tr:'İçeriklerde beğeni etkileşimi bulundu.','zh-CN':'在内容中发现点赞互动。',ru:'В контенте найдено взаимодействие лайками.'},
    'reportSignal.comment':{en:'Comment signal',tr:'Yorum işareti','zh-CN':'评论信号',ru:'Сигнал комментариев'},
    'reportSignal.commentText':{en:'Comment interaction was found in content.',tr:'İçeriklerde yorum etkileşimi bulundu.','zh-CN':'在内容中发现评论互动。',ru:'В контенте найдено взаимодействие комментариями.'},
    'reportSignal.tag':{en:'Tag signal',tr:'Etiket işareti','zh-CN':'标记信号',ru:'Сигнал отметки'},
    'reportSignal.tagText':{en:'A connection signal was found through a tag.',tr:'Etiket üzerinden bir bağlantı işareti bulundu.','zh-CN':'通过标记发现关联信号。',ru:'Через отметку найден сигнал связи.'},
    'reportSignal.coTagText':{en:'A co-tag signal was found in the same content.',tr:'Aynı içerikte birlikte etiketlenme işareti bulundu.','zh-CN':'在同一内容中发现共同标记信号。',ru:'В одном материале найден сигнал совместной отметки.'},
    'reportSignal.coTag':{en:'Co-tag',tr:'Ortak etiket','zh-CN':'共同标记',ru:'Совместная отметка'},
    'reportSignal.shareText':{en:'Appeared in share suggestions for the signed-in session.',tr:'Giriş yapılan oturumun paylaşım önerilerinde görüldü.','zh-CN':'出现在当前登录会话的分享推荐中。',ru:'Появился в рекомендациях отправки для текущего сеанса.'},
    'reportSignal.sharedAccounts':{en:'Shared accounts',tr:'Ortak hesaplar','zh-CN':'共同账户',ru:'Общие аккаунты'},
    'reportSignal.sharedAccountsText':{en:'Follower overlap with the signed-in test account was found.',tr:'Giriş yapılan test hesabıyla takipçi örtüşmesi bulundu.','zh-CN':'发现与已登录测试账户的粉丝重合。',ru:'Найдено пересечение подписчиков с тестовым аккаунтом.'},
    'target.viewerMutualFollowers':{en:'Followers shared with the test account',tr:'Test hesabıyla ortak takipçi','zh-CN':'与测试账户共同的粉丝',ru:'Общие подписчики с тестовым аккаунтом'},
    'target.viewerMutualFollowersNote':{en:'This count is relative to the signed-in test account, not the queried target.',tr:'Bu sayı sorgulanan hedefe değil, giriş yapılan test hesabına göredir.','zh-CN':'此数量相对于已登录的测试账户，而不是查询目标。',ru:'Это число относится к тестовому аккаунту, а не к искомой цели.'},
    'reportSignal.supportingMatch':{en:'Supporting match',tr:'Destekleyici eşleşme','zh-CN':'支持匹配',ru:'Подтверждающее совпадение'},
    'reportSignal.supportingMatchText':{en:'An additional match was found during analysis.',tr:'Analiz sırasında ek bir eşleşme bulundu.','zh-CN':'分析期间发现额外匹配。',ru:'Во время анализа найдено дополнительное совпадение.'},
    'report.probabilitySummaryTitle':{en:'Model confidence summary',tr:'Model güveni özeti','zh-CN':'模型置信度摘要',ru:'Сводка уверенности модели'},
    'report.graphUnavailable':{en:'Graph unavailable',tr:'Grafik kullanılamıyor','zh-CN':'网络图不可用',ru:'Граф недоступен'},
    'common.person':{en:'Person',tr:'kişi','zh-CN':'人员',ru:'Человек'},
    'detail.quickInfo':{en:'Quick information',tr:'Kısa bilgi','zh-CN':'简要信息',ru:'Краткая информация'},
    'report.graphBuildFailed':{en:'Network view could not be prepared',tr:'Ağ görüntüsü hazırlanamadı','zh-CN':'无法生成网络视图',ru:'Не удалось подготовить сетевую карту'},
    'report.graphBuildFailedText':{en:'Try redrawing it from the Network graph tab.',tr:'Network graph sekmesinden yeniden çizmeyi deneyin.','zh-CN':'请在“网络图”选项卡中尝试重新绘制。',ru:'Попробуйте перерисовать её на вкладке «Граф связей».'},
    'report.networkPreparing':{en:'Preparing network view…',tr:'Ağ görüntüsü hazırlanıyor…','zh-CN':'正在生成网络视图…',ru:'Подготавливается сетевая карта…'},
    'target.connectionUnavailable':{en:'Connection information unavailable',tr:'Bağlantı bilgisi alınamadı','zh-CN':'无法获取关联信息',ru:'Сведения о связи недоступны'},
    'target.connectionUnavailableText':{en:'Instagram returned an error for this data, so this scan produced no result.',tr:'Instagram içerikte hata döndürdüğü için bu taramada sonuç üretilmedi.','zh-CN':'Instagram 返回了此数据的错误，因此本次扫描未生成结果。',ru:'Instagram вернул ошибку для этих данных, поэтому сканирование не дало результата.'},
    'target.noVerifiedBirthday':{en:'No verified date',tr:'Doğrulanmış tarih yok','zh-CN':'没有已验证日期',ru:'Нет подтверждённой даты'},
    'target.noVerifiedBirthdayText':{en:'This response does not prove that the birthday is not today or that the system has an exact date.',tr:'Bu yanıt, doğum gününün bugün olmadığını veya sistemde kesin bir tarih bulunduğunu kanıtlamaz.','zh-CN':'此响应不能证明生日不是今天，也不能证明系统中有准确日期。',ru:'Этот ответ не доказывает, что день рождения не сегодня или что в системе есть точная дата.'},
    'target.visibilityDiffers':{en:'Visibility differs',tr:'Görünürlükler farklı','zh-CN':'可见性不同',ru:'Видимость различается'},
    'target.visibilityDiffersText':{en:'The Instagram profile appears private while the Threads profile appears public.',tr:'Instagram profili gizli, Threads profili ise herkese açık görünüyor.','zh-CN':'Instagram 资料似乎为私密，而 Threads 资料似乎为公开。',ru:'Профиль Instagram выглядит закрытым, а профиль Threads — открытым.'},
    'target.openThreads':{en:'Open Threads profile',tr:'Threads profilini aç','zh-CN':'打开 Threads 资料',ru:'Открыть профиль Threads'},
    'target.photoTechnicalIds':{en:'Technical photo identifiers',tr:'Fotoğrafın teknik kimlikleri','zh-CN':'照片技术标识符',ru:'Технические идентификаторы фотографии'},
    'target.showCountryCandidates':{en:'Show country candidates and relative scores',tr:'Ülke adaylarını ve göreli skorları göster','zh-CN':'显示候选国家/地区及相对分数',ru:'Показать страны-кандидаты и относительные оценки'},
    'target.taggedPlaces':{en:'Places seen in tags',tr:'Etiketlerde görülen yerler','zh-CN':'标记中出现的地点',ru:'Места из отметок'},
    'target.map':{en:'Map',tr:'Harita','zh-CN':'地图',ru:'Карта'},
    'target.bioPlaces':{en:'Location clues in the biography',tr:'Biyografideki yer işaretleri','zh-CN':'简介中的位置线索',ru:'Признаки места в описании'},
    'target.networkPhotoUploadHours':{en:'Network profile-photo upload times (UTC)',tr:'Ağdaki profil fotoğrafı yükleme saatleri (UTC / evrensel saat)','zh-CN':'网络头像上传时间（UTC）',ru:'Время загрузки фото профилей в сети (UTC)'},
    'target.networkPhotoHoursCaveat':{en:'This chart only shows the network’s overall time distribution; it does not prove the target’s time zone.',tr:'Bu grafik yalnız ağdaki genel saat dağılımıdır; hedefin saat dilimini kanıtlamaz.','zh-CN':'此图仅显示网络的整体时间分布，不能证明目标的时区。',ru:'График показывает лишь общее распределение времени в сети и не доказывает часовой пояс цели.'},
    'target.activityHours':{en:'Observed activity times (UTC)',tr:'Görülen etkinlik saatleri (UTC / evrensel saat)','zh-CN':'观察到的活动时间（UTC）',ru:'Наблюдаемое время активности (UTC)'},
    'target.activityHoursCaveat':{en:'With only a few records, this is a weak time clue.',tr:'Az sayıda kayıt varsa yalnız zayıf bir zaman ipucudur.','zh-CN':'记录较少时，这只是较弱的时间线索。',ru:'При малом числе записей это лишь слабый временной признак.'},
    'target.approxResult':{en:'Approximate result',tr:'Yaklaşık sonuç','zh-CN':'大致结果',ru:'Примерный результат'},
    'target.hiddenOrUnknown':{en:'Hidden / unknown',tr:'Gizli / bilinmiyor','zh-CN':'隐藏 / 未知',ru:'Скрыто / неизвестно'},
    'target.nametagEmoji':{en:'Profile nametag emoji',tr:'Profil etiketi emojisi','zh-CN':'资料名牌表情符号',ru:'Эмодзи именной метки профиля'},
    'target.nametagEmojiText':{en:'The emoji shown in the Instagram nametag design.',tr:'Instagram nametag tasarımında görülen emoji.','zh-CN':'Instagram 名牌设计中显示的表情符号。',ru:'Эмодзи, показанный в дизайне именной метки Instagram.'},
    'target.questionTemplates':{en:'Available question templates',tr:'Kullanılabilir soru şablonları','zh-CN':'可用问题模板',ru:'Доступные шаблоны вопросов'},
    'target.questionTemplatesText':{en:'These are Instagram’s ready-made choices, not answers supplied by the user.',tr:'Bunlar kullanıcının verdiği cevaplar değil, Instagram’ın sunduğu hazır seçeneklerdir.','zh-CN':'这些是 Instagram 提供的预设选项，并非用户给出的回答。',ru:'Это готовые варианты Instagram, а не ответы пользователя.'},
    'target.subscriptionFeatures':{en:'Subscription and revenue features',tr:'Abonelik ve gelir özellikleri','zh-CN':'订阅与收益功能',ru:'Функции подписки и дохода'},
    'target.noFacebookLink':{en:'No verified Facebook link was found in this scan',tr:'Bu taramada doğrulanmış Facebook bağlantısı bulunmadı','zh-CN':'本次扫描未找到已验证的 Facebook 关联',ru:'В этом сканировании не найдена подтверждённая связь с Facebook'},
    'target.noFacebookLinkText':{en:'Internal Meta identifiers are not public Facebook profile numbers.',tr:'Meta iç kimlikleri herkese açık Facebook profil numarası değildir.','zh-CN':'Meta 内部标识符不是公开的 Facebook 资料编号。',ru:'Внутренние идентификаторы Meta не являются публичными номерами профилей Facebook.'},
    'target.facebookCandidate':{en:'Facebook profile candidate',tr:'Facebook profil adayı','zh-CN':'Facebook 资料候选',ru:'Возможный профиль Facebook'},
    'target.samePersonUnverified':{en:'It has not been verified as the same person.',tr:'Aynı kişi olduğu doğrulanmamıştır.','zh-CN':'尚未验证为同一人。',ru:'Не подтверждено, что это тот же человек.'},
    'target.youFollowColumn':{en:'Test account follows',tr:'Test hesabı takip ediyor','zh-CN':'测试账户关注',ru:'Тестовый аккаунт подписан'},
    'target.followsYouColumn':{en:'Follows test account',tr:'Test hesabını takip ediyor','zh-CN':'关注测试账户',ru:'Подписан на тестовый аккаунт'},
    'target.favoriteShort':{en:'Favorite',tr:'Favori','zh-CN':'收藏',ru:'Избранное'},
    'target.mutedShort':{en:'Muted',tr:'Sessizde','zh-CN':'已静音',ru:'Без звука'},
    'target.blockedShort':{en:'Blocked',tr:'Engelli','zh-CN':'已屏蔽',ru:'Заблокирован'},
    'chip.closeFriend':{en:'close friend',tr:'yakın arkadaş','zh-CN':'密友',ru:'близкий друг'},
    'chip.followsTarget':{en:'follows target',tr:'hedefi takip ediyor','zh-CN':'关注目标',ru:'подписан на цель'},
    'chip.followedByTarget':{en:'followed by target',tr:'hedef takip ediyor','zh-CN':'目标关注',ru:'цель подписана'},
    'chip.signedInFollows':{en:'test account follows',tr:'test hesabı takip ediyor','zh-CN':'测试账户已关注',ru:'тестовый аккаунт подписан'},
    'chip.followsSignedIn':{en:'follows test account',tr:'test hesabını takip ediyor','zh-CN':'关注测试账户',ru:'подписан на тестовый аккаунт'},
    'chip.sharedFollowersTest':{en:'test shared: {count}',tr:'test ortak: {count}','zh-CN':'测试账户共同粉丝：{count}',ru:'общих с тестовым: {count}'},
    'chip.suggested':{en:'suggested',tr:'önerilen','zh-CN':'推荐',ru:'рекомендация'},
    'region.easternEuShort':{en:'Eastern Europe',tr:'Doğu Avrupa','zh-CN':'东欧',ru:'Восточная Европа'},
    'region.centralEuShort':{en:'Central Europe',tr:'Orta Avrupa','zh-CN':'中欧',ru:'Центральная Европа'},
  });

                                                                             
                                                                              
                                                                            
  sourceIndex.clear();
  for (const [key, row] of Object.entries(catalog)) {
    for (const phrase of Object.values(row)) {
      if (!String(phrase).includes('{')) sourceIndex.set(normalize(phrase), key);
    }
  }

  const sourceAliases = [
    ['verified','tier.verified'], ['doğrulanmış','tier.verified'], ['подтверждено','tier.verified'],
    ['high','tier.high'], ['yüksek','tier.high'], ['высокая','tier.high'],
    ['medium','tier.medium'], ['orta','tier.medium'], ['средняя','tier.medium'],
    ['low','tier.low'], ['düşük','tier.low'], ['низкая','tier.low'],
    ['noise','tier.noise'], ['yetersiz','tier.noise'], ['недостаточно','tier.noise'],
    ['unknown','tier.unknown'], ['bilinmiyor','tier.unknown'], ['неизвестно','tier.unknown'],
    ['high_probability','tier.high'], ['medium_probability','tier.medium'],
    ['low_probability','tier.low'],
    ['Eastern EU','region.easternEuShort'], ['Central EU','region.centralEuShort'],
    ['graph unavailable','report.graphUnavailable'],
    ['Kişi özeti','detail.personSummary'],
    ['Neden bu sonuç?','detail.why'],
    ['İlişki analizi raporu','report.analysisTitle'],
    ['Ağ görüntüsü','report.networkImage'],
    ['Bağlantıyı etkileyen işaretler','report.signalEyebrow'],
    ['Yakalanan bilgiler','report.capturedInfo'],
    ['Kişi','common.person'],
  ];
  for (const [phrase, key] of sourceAliases) sourceIndex.set(normalize(phrase), key);

  function escapeRegex(value) {
    return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  }

  function compileTemplate(template) {
    const compact = normalize(template);
    const names = [];
    let cursor = 0;
    let source = '^';
    for (const match of compact.matchAll(/\{([a-zA-Z0-9_]+)\}/g)) {
      source += escapeRegex(compact.slice(cursor, match.index)) + '(.+?)';
      names.push(match[1]);
      cursor = match.index + match[0].length;
    }
    if (!names.length) return null;
    source += escapeRegex(compact.slice(cursor)) + '$';
    return {regex:new RegExp(source, 'u'), names};
  }

  function parseTemplateVariable(name, value, sourceLocale) {
    if (!['count','current','total','visible','rank','found','years','months','hour','depth','sections'].includes(name)) {
      return value;
    }
    let normalized = String(value).trim().replace(/[\s\u00a0\u202f]/g, '');
    if (sourceLocale === 'tr' || sourceLocale === 'ru') {
      normalized = normalized.replace(/\./g, '').replace(',', '.');
    } else {
      normalized = normalized.replace(/,/g, '');
    }
    const number = Number(normalized);
    return Number.isFinite(number) ? number : value;
  }

  const templatePatterns = [];
  for (const [key, row] of Object.entries(catalog)) {
    for (const [sourceLocale, template] of Object.entries(row)) {
      const compiled = compileTemplate(template);
      if (compiled) templatePatterns.push({key, sourceLocale, ...compiled});
    }
  }

  function identifyText(value) {
    const compact = normalize(value);
    if (!compact) return null;
    const exact = sourceIndex.get(compact);
    if (exact) return {key:exact, vars:{}};
    for (const [regex, key, vars] of patterns) {
      const match = compact.match(regex);
      if (match) return {key, vars:vars(match)};
    }
    for (const {regex, key, names, sourceLocale} of templatePatterns) {
      const match = compact.match(regex);
      if (!match) continue;
      const vars = Object.create(null);
      names.forEach((name, index) => {
        vars[name] = parseTemplateVariable(name, match[index + 1], sourceLocale);
      });
      return {key, vars};
    }
    return null;
  }

  function translateText(value) {
    const binding = identifyText(value);
    return binding ? t(binding.key, binding.vars) : String(value ?? '');
  }

  function shouldSkip(node) {
    const parent = node && (node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement);
    if (!parent) return true;
    if (parent.closest('script,style,pre,code,[translate="no"],.no-i18n,[data-i18n-raw]')) return true;
                                                                               
                                                                              
    return Boolean(parent.matches([
      '.person-copy > strong', '.person-copy > span',
      '.rail-person-copy > strong', '.rail-person-copy > span',
      '.detail-identity-copy > strong', '.detail-identity-copy > span:not(.detail-eyebrow)',
      '.ti-hero-copy > h1', '.ti-hero-copy > strong', '.ti-hero-copy > p',
      '#detailUsername', '#detailPk', '#statTarget',
      '.node-username', '.node-full-name', '.node-label', '.node-initials', '.target-sub-label',
      '.report-person-identity strong',
      '.report-hero-copy h1', '.report-hero-copy > strong', '.report-hero-copy > p',
    ].join(',')));
  }

  function bindingMatches(binding, value) {
    const row = binding && catalog[binding.key];
    if (!row) return false;
    const compact = normalize(value);
    return Object.entries(row).some(([locale, message]) =>
      normalize(interpolate(message, binding.vars, locale)) === compact);
  }

  function translateTextNode(node) {
    if (!node || node.nodeType !== Node.TEXT_NODE || shouldSkip(node)) return;
    let binding = textBindings.get(node);
    if (binding && !bindingMatches(binding, node.nodeValue)) {
      textBindings.delete(node);
      binding = null;
    }
    if (!binding) {
      binding = identifyText(node.nodeValue);
      if (!binding) return;
      const leading = (node.nodeValue.match(/^\s*/) || [''])[0];
      const trailing = (node.nodeValue.match(/\s*$/) || [''])[0];
      binding = {...binding, leading, trailing};
      textBindings.set(node, binding);
    }
    const next = `${binding.leading}${t(binding.key, binding.vars)}${binding.trailing}`;
    if (node.nodeValue !== next) node.nodeValue = next;
  }

  function translateElement(element) {
    if (!element || element.nodeType !== Node.ELEMENT_NODE || shouldSkip(element)) return;
    const textKey = element.dataset.i18n;
    if (textKey && catalog[textKey]) {
      const next = t(textKey);
      if (element.textContent !== next) element.textContent = next;
    }
    const attrs = ['placeholder', 'title', 'aria-label'];
    let bindings = attributeBindings.get(element);
    if (!bindings) {
      bindings = Object.create(null);
      attributeBindings.set(element, bindings);
    }
    for (const attr of attrs) {
      const datasetKey = `i18n${attr.split('-').map(part => part[0].toUpperCase() + part.slice(1)).join('')}`;
      const explicit = element.dataset[datasetKey];
      const current = element.getAttribute(attr);
      if (explicit && catalog[explicit]) {
        bindings[attr] = {key:explicit, vars:{}};
      } else if (bindings[attr] && !bindingMatches(bindings[attr], current)) {
                                                                          
                                                             
        bindings[attr] = identifyText(current);
      } else if (!bindings[attr] && element.hasAttribute(attr)) {
        bindings[attr] = identifyText(current);
      }
      const binding = bindings[attr];
      if (binding) {
        const next = t(binding.key, binding.vars);
        if (element.getAttribute(attr) !== next) element.setAttribute(attr, next);
      }
    }
  }

  function translate(root=document) {
    if (!root) return;
    if (root.nodeType === Node.TEXT_NODE) {
      translateTextNode(root);
      return;
    }
    if (root.nodeType === Node.ELEMENT_NODE) translateElement(root);
    const scope = root.nodeType === Node.DOCUMENT_NODE ? root.documentElement : root;
    if (!scope || !scope.querySelectorAll) return;
    scope.querySelectorAll('[data-i18n],[data-i18n-placeholder],[data-i18n-title],[data-i18n-aria-label],[placeholder],[title],[aria-label]')
      .forEach(translateElement);
    const walker = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT);
    let node;
    while ((node = walker.nextNode())) translateTextNode(node);
  }

  function getLocale() { return currentLocale; }
  function getFormatLocale() { return FORMAT_LOCALE[currentLocale] || FORMAT_LOCALE.en; }
  function formatNumber(value, options={}) {
    const number = Number(value);
    if (!Number.isFinite(number)) return String(value ?? '');
    return new Intl.NumberFormat(getFormatLocale(), options).format(number);
  }
  function formatPercent(value, options={}) {
    const number = Number(value);
    if (!Number.isFinite(number)) return String(value ?? '');
    const maximumFractionDigits = Number.isInteger(number) ? 0 : 1;
    return new Intl.NumberFormat(getFormatLocale(), {
      style:'percent', maximumFractionDigits, ...options,
    }).format(number / 100);
  }
  function formatDate(value, options={dateStyle:'medium'}) {
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) return '';
    return new Intl.DateTimeFormat(getFormatLocale(), options).format(date);
  }
  function compareText(a, b) {
    return String(a ?? '').localeCompare(String(b ?? ''), getFormatLocale(), {sensitivity:'base'});
  }

  const TIER_KEYS = Object.freeze({
    verified:'tier.verified', intimate:'tier.verified', '1hop_stable':'tier.verified',
    high_probability:'tier.high', known:'tier.high', '1hop_strong':'tier.high',
    medium_probability:'tier.medium', acquaintance:'tier.medium', '1hop_confirmed':'tier.medium',
    low_probability:'tier.low', algorithmic:'tier.low', '1hop_likely':'tier.low',
    noise:'tier.noise', '2hop_suspect':'tier.noise', unknown:'tier.unknown',
  });
  function tierLabel(value) {
    return t(TIER_KEYS[String(value || '').toLowerCase()] || 'tier.unknown');
  }

  function setLocale(next, {persist=true, announce=true}={}) {
    const locale = normalizeLocale(next);
    currentLocale = locale;
    document.documentElement.lang = HTML_LANG[locale];
    document.documentElement.dataset.locale = locale;
    const select = document.getElementById('languageSelect');
    if (select && select.value !== locale) select.value = locale;
    if (persist) {
      try { localStorage.setItem(STORAGE_KEY, locale); } catch (_) {                                     }
    }
    translate(document);
    if (announce) document.dispatchEvent(new CustomEvent('app:localechange', {detail:{locale}}));
    return locale;
  }

  function init() {
    if (initialized || !document.body) return;
    initialized = true;
    const select = document.getElementById('languageSelect');
    if (select) {
      select.value = currentLocale;
      select.addEventListener('change', event => setLocale(event.target.value));
    }
    setLocale(currentLocale, {persist:false, announce:false});
    observer = new MutationObserver(records => {
      for (const record of records) {
        if (record.type === 'characterData') translateTextNode(record.target);
        if (record.type === 'attributes') translateElement(record.target);
        for (const node of record.addedNodes || []) translate(node);
      }
    });
    observer.observe(document.body, {
      subtree:true, childList:true, characterData:true, attributes:true,
      attributeFilter:['placeholder','title','aria-label'],
    });
  }

  window.AppI18n = Object.freeze({
    t, translate, translateText, setLocale, getLocale, getFormatLocale,
    formatNumber, formatPercent, formatDate, compareText, tierLabel,
    locales:Object.freeze(['en','tr','zh-CN','ru']),
  });

  if (document.body) {
    init();
  } else if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init, {once:true});
  } else {
    init();
  }
})();
