const API = window.location.origin;

        const CACHE_KEY = 'disciplinas_cache';
        const CONTEUDOS_CACHE_PREFIX = 'conteudos_cache_';
        const CONTAGENS_CACHE_PREFIX = 'contagens_conteudos_cache_';
        const CACHE_TTL = 1000 * 60 * 60;

        const disciplinaSelect = document.getElementById("disciplina");
        const serieSelect = document.getElementById("serie");
        const serieAviso = document.getElementById("serieAviso");
        const conteudosSelect = document.getElementById("conteudos");
        const conteudosLista = document.getElementById("conteudosLista");
        const conteudosResumo = document.getElementById("conteudosResumo");
        const buscarConteudo = document.getElementById("buscarConteudo");
        const selecionarTodosConteudos = document.getElementById("selecionarTodosConteudos");
        const limparConteudos = document.getElementById("limparConteudos");
        const form = document.getElementById("atividadeForm");
        const statusDiv = document.getElementById("status");
        const previewModal = document.getElementById("previewModal");
        const previewResumo = document.getElementById("previewResumo");
        const previewStats = document.getElementById("previewStats");
        const previewQuestoes = document.getElementById("previewQuestoes");
        const previewFechar = document.getElementById("previewFechar");
        const previewGerarPdf = document.getElementById("previewGerarPdf");
        const previewTitulo = document.getElementById("previewTitulo");
        const previewDisciplina = document.getElementById("previewDisciplina");
        const previewProfessor = document.getElementById("previewProfessor");
        const previewData = document.getElementById("previewData");
        const previewSerie = document.getElementById("previewSerie");

        let conteudosDisponiveis = [];
        let conteudosArvore = [];
        let conteudosSelecionados = new Set();
        let conteudosExpandidos = new Set();
        let previewAtual = null;
        let disciplinasDisponiveis = [];
        let contagensConteudos = null;

        // Mostrar/ocultar aviso de série
        serieSelect.addEventListener("change", () => {
            if (serieSelect.value) {
                serieAviso.classList.remove("hidden");
            } else {
                serieAviso.classList.add("hidden");
            }

            preencherDisciplinas(disciplinasDisponiveis);
        });

        function setStatus(mensagem, tipo) {
            statusDiv.classList.remove("hidden", "bg-blue-50", "text-blue-700", "bg-red-50", "text-red-700", "bg-green-50", "text-green-700");
            if (tipo === "loading") statusDiv.classList.add("bg-blue-50", "text-blue-700");
            else if (tipo === "error") statusDiv.classList.add("bg-red-50", "text-red-700");
            else if (tipo === "success") statusDiv.classList.add("bg-green-50", "text-green-700");
            statusDiv.innerHTML = mensagem;
        }

        function registrarErro(contexto, erro, extra = {}) {
            console.groupCollapsed(`[QFund] ${contexto}`);
            console.error(erro);
            if (Object.keys(extra).length) console.info("contexto", extra);
            console.groupEnd();
        }

        function textoErro(erro, fallback) {
            const mensagem = erro && erro.message ? erro.message : String(erro || "");

            try {
                const parsed = JSON.parse(mensagem);
                if (parsed.detail) return parsed.detail;
            } catch (e) {}

            return mensagem || fallback;
        }

        async function fetchJson(url, options = {}, contexto = "requisição") {
            const response = await fetch(url, options);
            if (!response.ok) {
                const body = await response.text();
                throw new Error(body || `${contexto} falhou (${response.status})`);
            }

            return response.json();
        }

        async function fetchBlob(url, options = {}, contexto = "download") {
            const response = await fetch(url, options);
            if (!response.ok) {
                const body = await response.text();
                throw new Error(body || `${contexto} falhou (${response.status})`);
            }

            return response.blob();
        }

        async function carregarDisciplinas() {
            try {
                const cached = localStorage.getItem(CACHE_KEY);
                if (cached) {
                    const parsed = JSON.parse(cached);
                    if (Date.now() - parsed.ts < CACHE_TTL) {
                        disciplinasDisponiveis = parsed.data || [];
                        preencherDisciplinas(disciplinasDisponiveis);
                        return;
                    }
                }

                const data = await fetchJson(`${API}/disciplinas`, {}, "carregar disciplinas");
                const disciplinas = data.data || data;
                disciplinasDisponiveis = disciplinas;

                try {
                    localStorage.setItem(CACHE_KEY, JSON.stringify({ ts: Date.now(), data: disciplinas }));
                } catch (e) {}

                preencherDisciplinas(disciplinasDisponiveis);
            } catch (erro) {
                registrarErro("Erro ao carregar disciplinas", erro);
                setStatus(`<i class="fas fa-exclamation-circle"></i> ${textoErro(erro, "Erro ao carregar disciplinas.")}`, 'error');
            }
        }

        function preencherDisciplinas(disciplinas) {
            const selecionada = disciplinaSelect.value;
            const serie = serieSelect.value;
            const disciplinasFiltradas = filtrarDisciplinasPorSerie(disciplinas, serie);

            disciplinaSelect.innerHTML = serie
                ? '<option value="">Selecione...</option>'
                : '<option value="">Escolha a série primeiro</option>';
            disciplinaSelect.disabled = !serie;

            disciplinasFiltradas.forEach(disciplina => {
                disciplinaSelect.innerHTML += `<option value="${disciplina.id}">${disciplina.name}</option>`;
            });

            const aindaDisponivel = disciplinasFiltradas.some(
                (disciplina) => String(disciplina.id) === String(selecionada)
            );

            if (selecionada && aindaDisponivel) {
                disciplinaSelect.value = selecionada;
                return;
            }

            disciplinaSelect.value = "";
            carregarConteudos("");
        }

        function filtrarDisciplinasPorSerie(disciplinas, serie) {
            if (!serie) return [];

            const idsOcultosEnsinoFundamental = new Set(["2", "4", "5", "12", "13", "21"]);
            const idsOcultosEnsinoMedio = new Set(["17", "19"]);
            const ocultos = serie.startsWith("EF")
                ? idsOcultosEnsinoFundamental
                : idsOcultosEnsinoMedio;

            return (disciplinas || []).filter(
                (disciplina) => !ocultos.has(String(disciplina.id))
            );
        }

        function escapeHtml(texto) {
            return String(texto)
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        function normalizarConteudos(conteudos, nivel = 0, caminho = [], caminhoIds = []) {
            const lista = [];
            const arvore = [];

            conteudos.forEach((conteudo) => {
                const nome = conteudo.name || conteudo.nome || "Conteúdo sem nome";
                const filhos = conteudo.subitens || conteudo.children || [];
                const item = {
                    id: String(conteudo.id),
                    nome,
                    grupo: caminho[caminho.length - 1] || "",
                    caminho: [...caminho, nome].join(" > "),
                    caminhoIds: [...caminhoIds, String(conteudo.id)],
                    nivel,
                    quantidadeQuestoes: null,
                    filhos: [],
                    descendentes: []
                };

                if (Array.isArray(filhos) && filhos.length) {
                    const filhosNormalizados = normalizarConteudos(
                        filhos,
                        nivel + 1,
                        [...caminho, nome],
                        [...caminhoIds, String(conteudo.id)]
                    );
                    item.filhos = filhosNormalizados.arvore;
                    item.descendentes = filhosNormalizados.lista.map((filho) => filho.id);
                    lista.push(item, ...filhosNormalizados.lista);
                } else {
                    lista.push(item);
                }

                arvore.push(item);
            });

            return { lista, arvore };
        }

        function atualizarSelectConteudos() {
            conteudosSelect.innerHTML = "";
            conteudosDisponiveis.forEach((conteudo) => {
                const option = document.createElement("option");
                option.value = conteudo.id;
                option.textContent = conteudo.nome;
                option.selected = conteudosSelecionados.has(conteudo.id);
                conteudosSelect.appendChild(option);
            });
        }

        function atualizarResumoConteudos(totalVisivel = conteudosDisponiveis.length) {
            const selecionados = conteudosSelecionados.size;

            if (!conteudosDisponiveis.length) {
                conteudosResumo.textContent = disciplinaSelect.value
                    ? "Não achei conteúdos para essa matéria."
                    : "Escolha uma matéria para eu mostrar os conteúdos.";
                return;
            }

            const pluralEncontrados = totalVisivel === 1 ? "conteúdo" : "conteúdos";

            if (selecionados) {
                const pluralMarcados = selecionados === 1 ? "conteúdo marcado" : "conteúdos marcados";
                conteudosResumo.textContent = `${selecionados} ${pluralMarcados}. Estou mostrando ${totalVisivel} ${pluralEncontrados}.`;
                return;
            }

            conteudosResumo.textContent = `Encontrei ${totalVisivel} ${pluralEncontrados}. Marque os que entram na atividade.`;
        }

        function renderizarConteudos() {
            const termo = (buscarConteudo.value || "").trim().toLowerCase();
            const filtrados = conteudosDisponiveis.filter((conteudo) => {
                const texto = `${conteudo.nome} ${conteudo.grupo} ${conteudo.caminho}`.toLowerCase();
                return texto.includes(termo);
            });

            conteudosLista.innerHTML = "";

            if (!conteudosDisponiveis.length) {
                conteudosLista.innerHTML = `
                    <div class="h-[126px] flex items-center justify-center text-sm text-gray-500">
                        <span>Os conteúdos aparecerão aqui.</span>
                    </div>`;
                atualizarResumoConteudos(0);
                return;
            }

            if (!filtrados.length) {
                conteudosLista.innerHTML = `
                    <div class="h-[126px] flex items-center justify-center text-sm text-gray-500">
                        <span>Nenhum conteúdo encontrado.</span>
                    </div>`;
                atualizarResumoConteudos(0);
                return;
            }

            const container = document.createElement("div");
            container.className = termo
                ? "grid grid-cols-1 md:grid-cols-2 gap-2"
                : "space-y-1";

            const criarItem = (conteudo, modoBusca = false) => {
                const selecionado = conteudosSelecionados.has(conteudo.id);
                const temFilhos = conteudo.filhos && conteudo.filhos.length;
                const expandido = conteudosExpandidos.has(conteudo.id);
                const button = document.createElement("button");
                button.type = "button";
                button.dataset.id = conteudo.id;
                button.style.marginLeft = modoBusca ? "0" : `${conteudo.nivel * 18}px`;
                button.className = [
                    "w-full text-left rounded-lg border p-3 transition-all min-h-[58px]",
                    "focus:outline-none focus:ring-2 focus:ring-blue-500",
                    selecionado
                        ? "border-blue-500 bg-blue-50 shadow-sm"
                        : "border-gray-200 bg-white hover:border-blue-300 hover:bg-white"
                ].join(" ");

                button.innerHTML = `
                    <div class="flex items-start gap-3">
                        <span class="expand-control w-5 shrink-0 text-gray-500">
                            ${temFilhos && !modoBusca ? `<i class="fas ${expandido ? "fa-chevron-down" : "fa-chevron-right"} text-[11px]"></i>` : ""}
                        </span>
                        <span class="mt-0.5 w-5 h-5 rounded-md border flex items-center justify-center shrink-0 ${selecionado ? "bg-blue-600 border-blue-600 text-white" : "bg-white border-gray-300 text-transparent"}">
                            <i class="fas fa-check text-[11px]"></i>
                        </span>
                        <span class="min-w-0">
                            <span class="block text-sm font-semibold ${selecionado ? "text-blue-800" : "text-gray-800"}">${escapeHtml(conteudo.nome)}</span>
                            ${conteudo.grupo ? `<span class="block text-xs text-gray-500 mt-1">${escapeHtml(modoBusca ? conteudo.caminho : conteudo.grupo)}</span>` : ""}
                        </span>
                        <span class="ml-auto shrink-0 rounded-full px-2 py-1 text-[11px] font-bold ${classeBadgeContagem(conteudo)}">
                            ${textoBadgeContagem(conteudo)}
                        </span>
                    </div>`;

                button.addEventListener("click", (event) => {
                    if (temFilhos && !modoBusca && event.target.closest(".expand-control")) {
                        if (conteudosExpandidos.has(conteudo.id)) {
                            conteudosExpandidos.delete(conteudo.id);
                        } else {
                            conteudosExpandidos.add(conteudo.id);
                        }
                    } else {
                        alternarConteudo(conteudo);
                    }
                    atualizarSelectConteudos();
                    renderizarConteudos();
                });

                container.appendChild(button);
            };

            const renderizarNo = (conteudo) => {
                criarItem(conteudo, false);
                if (conteudosExpandidos.has(conteudo.id)) {
                    conteudo.filhos.forEach(renderizarNo);
                }
            };

            if (termo) {
                filtrados.forEach((conteudo) => criarItem(conteudo, true));
            } else {
                conteudosArvore.forEach(renderizarNo);
            }

            conteudosLista.appendChild(container);
            atualizarResumoConteudos(filtrados.length);
        }

        function alternarConteudo(conteudo) {
            const ids = [conteudo.id, ...(conteudo.descendentes || [])];
            const deveSelecionar = !ids.every((id) => conteudosSelecionados.has(id));
            ids.forEach((id) => {
                if (deveSelecionar) {
                    conteudosSelecionados.add(id);
                } else {
                    conteudosSelecionados.delete(id);
                }
            });
            if (deveSelecionar && conteudo.filhos && conteudo.filhos.length) {
                conteudosExpandidos.add(conteudo.id);
            }
        }

        function setConteudosHabilitados(habilitado) {
            buscarConteudo.disabled = !habilitado;
            selecionarTodosConteudos.disabled = !habilitado;
            limparConteudos.disabled = !habilitado;
        }

        async function carregarConteudos(disciplinaId) {
            conteudosSelect.innerHTML = "";
            conteudosDisponiveis = [];
            conteudosArvore = [];
            conteudosSelecionados = new Set();
            conteudosExpandidos = new Set();
            contagensConteudos = null;
            buscarConteudo.value = "";
            setConteudosHabilitados(false);
            renderizarConteudos();

            if (!disciplinaId) return;

            try {
                const cacheKey = `${CONTEUDOS_CACHE_PREFIX}${disciplinaId}`;
                const cached = localStorage.getItem(cacheKey);
                if (cached) {
                    const parsed = JSON.parse(cached);
                    if (Date.now() - parsed.ts < CACHE_TTL) {
                        aplicarConteudos(parsed.data);
                        carregarContagensConteudos(disciplinaId).catch((erro) => {
                            registrarErro("Erro ao carregar contagens dos conteúdos", erro, { disciplinaId });
                        });
                        return;
                    }
                }

                conteudosLista.innerHTML = `
                    <div class="h-[126px] flex items-center justify-center text-sm text-blue-700">
                        <i class="fas fa-spinner fa-spin mr-2"></i>
                        <span>Carregando conteúdos...</span>
                    </div>`;

                const conteudos = await fetchJson(`${API}/conteudos/${disciplinaId}`, {}, "carregar conteúdos");

                try {
                    localStorage.setItem(cacheKey, JSON.stringify({ ts: Date.now(), data: conteudos }));
                } catch (e) {}

                aplicarConteudos(conteudos);
                carregarContagensConteudos(disciplinaId).catch((erro) => {
                    registrarErro("Erro ao carregar contagens dos conteúdos", erro, { disciplinaId });
                });
            } catch (erro) {
                registrarErro("Erro ao carregar conteúdos", erro, { disciplinaId });
                setStatus(`<i class="fas fa-exclamation-circle"></i> ${textoErro(erro, "Erro ao carregar conteúdos.")}`, 'error');
            }
        }

        function aplicarConteudos(conteudos) {
            const conteudosNormalizados = normalizarConteudos(Array.isArray(conteudos) ? conteudos : []);
            conteudosDisponiveis = conteudosNormalizados.lista;
            conteudosArvore = conteudosNormalizados.arvore;
            setConteudosHabilitados(conteudosDisponiveis.length > 0);
            atualizarSelectConteudos();
            renderizarConteudos();
        }

        async function carregarContagensConteudos(disciplinaId) {
            if (!disciplinaId || !serieSelect.value) return;

            const cacheKey = `${CONTAGENS_CACHE_PREFIX}${disciplinaId}_${serieSelect.value}`;
            const cached = localStorage.getItem(cacheKey);

            if (cached) {
                const parsed = JSON.parse(cached);
                if (Date.now() - parsed.ts < CACHE_TTL) {
                    aplicarContagensConteudos(parsed.data.contagens || {});
                    return;
                }
            }

            contagensConteudos = null;
            renderizarConteudos();

            const params = new URLSearchParams({
                serie: serieSelect.value
            });
            const data = await fetchJson(
                `${API}/conteudos/${disciplinaId}/contagens?${params.toString()}`,
                {},
                "carregar quantidades por conteúdo"
            );

            try {
                localStorage.setItem(cacheKey, JSON.stringify({ ts: Date.now(), data }));
            } catch (e) {}

            aplicarContagensConteudos(data.contagens || {});
        }

        function aplicarContagensConteudos(contagens) {
            contagensConteudos = contagens || {};

            conteudosDisponiveis.forEach((conteudo) => {
                conteudo.quantidadeQuestoes = Number(contagensConteudos[conteudo.id] || 0);
            });

            renderizarConteudos();
        }

        function textoBadgeContagem(conteudo) {
            if (conteudo.quantidadeQuestoes === null || conteudo.quantidadeQuestoes === undefined) {
                return "...";
            }

            const total = Number(conteudo.quantidadeQuestoes || 0);
            return total === 1 ? "1 questão" : `${total} questões`;
        }

        function classeBadgeContagem(conteudo) {
            if (conteudo.quantidadeQuestoes === null || conteudo.quantidadeQuestoes === undefined) {
                return "bg-slate-100 text-slate-500";
            }

            return Number(conteudo.quantidadeQuestoes || 0) > 0
                ? "bg-emerald-50 text-emerald-700"
                : "bg-amber-50 text-amber-700";
        }

        disciplinaSelect.addEventListener("change", () => carregarConteudos(disciplinaSelect.value));
        buscarConteudo.addEventListener("input", renderizarConteudos);

        selecionarTodosConteudos.addEventListener("click", () => {
            const termo = (buscarConteudo.value || "").trim().toLowerCase();
            conteudosDisponiveis
                .filter((conteudo) => `${conteudo.nome} ${conteudo.grupo} ${conteudo.caminho}`.toLowerCase().includes(termo))
                .forEach((conteudo) => conteudosSelecionados.add(conteudo.id));
            atualizarSelectConteudos();
            renderizarConteudos();
        });

        limparConteudos.addEventListener("click", () => {
            conteudosSelecionados = new Set();
            atualizarSelectConteudos();
            renderizarConteudos();
        });

        function montarPayloadAtividade() {
            const tipoVal = document.getElementById("tipo_usuario").value || null;
            const body = {
                disciplina_id: disciplinaSelect.value,
                conteudos: montarConteudosSelecionadosPayload(),
                quantidade: Number(document.getElementById("quantidade").value),
                dificuldade: document.getElementById("dificuldade").value || null,
                tipo: document.getElementById("tipo").value || null,
                incluir_gabarito: document.getElementById("gabarito").checked,
                titulo: document.getElementById("titulo").value,
                serie: serieSelect.value || null
            };

            if (tipoVal) body.tipo_usuario = tipoVal;
            if (tipoVal === "professor") {
                body.professor = document.getElementById("professor").value || null;
            }

            return body;
        }

        function montarConteudosSelecionadosPayload() {
            const selecionados = conteudosDisponiveis.filter((conteudo) => {
                if (!conteudosSelecionados.has(conteudo.id)) return false;

                const ancestraisSelecionados = (conteudo.caminhoIds || [])
                    .slice(0, -1)
                    .some((id) => conteudosSelecionados.has(id));

                return !ancestraisSelecionados;
            });

            return selecionados.map((conteudo) => conteudo.caminho || conteudo.nome);
        }

        function abrirPreviewModal() {
            previewModal.classList.remove("hidden");
            document.body.classList.add("overflow-hidden");
        }

        function fecharPreviewModal() {
            previewModal.classList.add("hidden");
            document.body.classList.remove("overflow-hidden");
        }

        function renderizarPreview(data) {
            previewAtual = data;
            abrirPreviewModal();

            const stats = data.estatisticas || {};
            const dificuldades = Object.entries(stats.dificuldades || {})
                .map(([nome, total]) => `${escapeHtml(nome)}: <b>${total}</b>`)
                .join("<br>");

            const quantidadeSolicitada = data.quantidade_solicitada || (data.meta && data.meta.quantidade) || data.quantidade;
            const avisos = data.avisos || [];
            const avisosHtml = avisos
                .map((aviso) => `
                    <div class="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                        <div class="font-bold">Atenção</div>
                        <div class="mt-1">${escapeHtml(aviso.mensagem || "")}</div>
                    </div>
                `)
                .join("");

            previewResumo.textContent = `${data.quantidade} de ${quantidadeSolicitada} questões na prévia · ${data.reservas || 0} reservas para troca`;
            previewTitulo.textContent = ((data.meta && data.meta.titulo) || "Atividade").toUpperCase();
            previewDisciplina.textContent = data.disciplina || "-";
            previewProfessor.textContent = (data.meta && data.meta.professor) || "-";
            previewData.textContent = (data.meta && data.meta.data_avaliacao) || new Date().toLocaleDateString("pt-BR");
            previewSerie.textContent = formatarSerie((data.meta && data.meta.serie) || "");
            previewGerarPdf.disabled = !data.questoes || !data.questoes.length;
            previewGerarPdf.classList.toggle("opacity-50", previewGerarPdf.disabled);
            previewGerarPdf.classList.toggle("cursor-not-allowed", previewGerarPdf.disabled);

            previewStats.innerHTML = `
                ${avisosHtml}
                <div class="rounded-lg border border-slate-200 p-4">
                    <div class="text-xs font-bold text-slate-500 uppercase">Resumo</div>
                    <div class="mt-3 grid grid-cols-2 gap-2 text-sm">
                        <div class="rounded bg-slate-50 p-3"><b>${data.quantidade}</b><br><span class="text-slate-500">de ${quantidadeSolicitada}</span></div>
                        <div class="rounded bg-slate-50 p-3"><b>${data.reservas || 0}</b><br><span class="text-slate-500">reservas</span></div>
                        <div class="rounded bg-slate-50 p-3"><b>${stats.objetivas || 0}</b><br><span class="text-slate-500">objetivas</span></div>
                        <div class="rounded bg-slate-50 p-3"><b>${stats.discursivas || 0}</b><br><span class="text-slate-500">discursivas</span></div>
                    </div>
                </div>
                <div class="rounded-lg border border-slate-200 p-4 text-sm">
                    <div class="text-xs font-bold text-slate-500 uppercase mb-2">Dificuldades</div>
                    ${dificuldades || "<span class='text-slate-500'>Sem dados</span>"}
                </div>
                <div class="rounded-lg border border-slate-200 p-4 text-sm">
                    <div class="text-xs font-bold text-slate-500 uppercase mb-2">Imagens</div>
                    ${stats.com_imagem || 0} questões com imagem
                </div>
            `;

            previewQuestoes.innerHTML = "";

            if (!data.questoes || !data.questoes.length) {
                previewQuestoes.innerHTML = `
                    <div class="rounded-lg border border-amber-200 bg-amber-50 text-amber-800 p-4 text-sm">
                        Nenhuma questão encontrada para esses filtros. Ajuste a série, disciplina, conteúdo ou dificuldade para gerar o PDF.
                    </div>`;
                return;
            }

            data.questoes.forEach((questao) => {
                const card = document.createElement("article");
                card.className = "border border-slate-200 rounded-lg p-4 md:p-5";
                card.dataset.questaoId = questao.id;

                const alternativas = (questao.alternativas || [])
                    .map((alt) => `<div class="mt-1">${escapeHtml(alt)}</div>`)
                    .join("");

                const imagens = (questao.imagens || [])
                    .map((src) => `<img src="${escapeHtml(src)}" class="my-3 max-h-64 max-w-full object-contain border border-slate-200 rounded" alt="">`)
                    .join("");

                const meta = [
                    questao.tipo,
                    questao.dificuldade,
                    questao.conteudo
                ].filter(Boolean).map(escapeHtml).join(" · ");

                card.innerHTML = `
                    <div class="flex flex-col md:flex-row md:items-start md:justify-between gap-3">
                        <div class="min-w-0">
                            <div class="text-xs text-slate-500 mb-2">${meta}</div>
                            <div class="font-semibold text-slate-900 leading-relaxed">${questao.numero}. ${escapeHtml(questao.enunciado || "")}</div>
                        </div>
                        <div class="flex gap-2 shrink-0">
                            <button type="button" class="trocar-questao inline-flex items-center gap-2 rounded-lg border border-blue-200 text-blue-700 bg-blue-50 hover:bg-blue-100 px-3 py-2 text-xs font-bold">
                                <i class="fas fa-sync-alt"></i> Trocar
                            </button>
                            <button type="button" class="remover-questao inline-flex items-center gap-2 rounded-lg border border-red-200 text-red-700 bg-red-50 hover:bg-red-100 px-3 py-2 text-xs font-bold">
                                <i class="fas fa-trash"></i> Remover
                            </button>
                        </div>
                    </div>
                    ${imagens}
                    <div class="mt-3 text-sm leading-relaxed">${alternativas}</div>
                    ${questao.tipo === "discursiva" ? "<div class='mt-4 space-y-3'><div class='border-b border-slate-300 h-5'></div><div class='border-b border-slate-300 h-5'></div><div class='border-b border-slate-300 h-5'></div></div>" : ""}
                `;

                card.querySelector(".trocar-questao").addEventListener("click", () => trocarQuestaoPreview(questao.id));
                card.querySelector(".remover-questao").addEventListener("click", () => removerQuestaoPreview(questao.id));
                previewQuestoes.appendChild(card);
            });
        }

        async function trocarQuestaoPreview(questaoId) {
            if (!previewAtual) return;

            try {
                previewResumo.textContent = "Trocando questão...";
                const data = await fetchJson(`${API}/previsualizar-atividade/trocar`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ preview_id: previewAtual.preview_id, questao_id: questaoId })
                }, "trocar questão");

                renderizarPreview(data);
            } catch (erro) {
                registrarErro("Erro ao trocar questão da prévia", erro, { questaoId });
                alert(textoErro(erro, "Não consegui trocar essa questão. Talvez não haja reserva compatível."));
            }
        }

        async function removerQuestaoPreview(questaoId) {
            if (!previewAtual) return;

            try {
                const data = await fetchJson(`${API}/previsualizar-atividade/remover`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ preview_id: previewAtual.preview_id, questao_id: questaoId })
                }, "remover questão");

                renderizarPreview(data);
            } catch (erro) {
                registrarErro("Erro ao remover questão da prévia", erro, { questaoId });
                alert(textoErro(erro, "Não consegui remover essa questão."));
            }
        }

        async function gerarPdfDaPreview() {
            if (!previewAtual) return;
            if (!previewAtual.questoes || !previewAtual.questoes.length) {
                alert("Não há questões na prévia para gerar o PDF.");
                return;
            }

            previewGerarPdf.disabled = true;
            previewGerarPdf.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Gerando...';

            try {
                const blob = await fetchBlob(`${API}/gerar-atividade-preview`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ preview_id: previewAtual.preview_id })
                }, "gerar PDF");

                const url = window.URL.createObjectURL(blob);
                const link = document.createElement("a");
                link.href = url;
                link.download = "atividade.pdf";
                document.body.appendChild(link);
                link.click();
                link.remove();
                window.URL.revokeObjectURL(url);

                fecharPreviewModal();
                setStatus('<i class="fas fa-check-circle mr-2"></i> PDF gerado com sucesso!', 'success');
            } catch (erro) {
                registrarErro("Erro ao gerar PDF da prévia", erro);
                alert(textoErro(erro, "Erro ao gerar o PDF da prévia."));
            } finally {
                previewGerarPdf.disabled = false;
                previewGerarPdf.innerHTML = '<i class="fas fa-file-pdf"></i> Gerar PDF';
            }
        }

        previewFechar.addEventListener("click", fecharPreviewModal);
        previewGerarPdf.addEventListener("click", gerarPdfDaPreview);

        form.addEventListener("submit", async function (e) {
            e.preventDefault();

            if (serieSelect.value) {
                setStatus('<i class="fas fa-spinner fa-spin mr-2"></i> Gerando atividade com filtro de série...', 'loading');
            } else {
                setStatus('<i class="fas fa-spinner fa-spin mr-2"></i> Gerando atividade...', 'loading');
            }

            try {
                const data = await fetchJson(`${API}/previsualizar-atividade`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(montarPayloadAtividade())
                }, "montar prévia");

                renderizarPreview(data);
                statusDiv.classList.add("hidden");

            } catch (erro) {
                registrarErro("Erro ao montar prévia", erro, montarPayloadAtividade());
                setStatus(`<i class="fas fa-times-circle mr-2"></i> ${textoErro(erro, "Erro ao montar a prévia.")}`, 'error');
            }
        });

        // Perfil do usuário
        const tipoSelect = document.getElementById('tipo_usuario');
        const professorField = document.getElementById('professorField');
        const professorInput = document.getElementById('professor');

        async function saveProfile() {
            const tipo = tipoSelect ? (tipoSelect.value || null) : null;
            const nome = (tipo === 'professor' && professorInput) ? (professorInput.value || null) : null;
            const disciplina_preferida = disciplinaSelect.value || null;
            const profile = { tipo: tipo || 'usuario', nome, disciplina_preferida };
            try {
                await fetchJson(`${API}/usuario`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(profile)
                }, "salvar perfil");
            } catch (e) {
                registrarErro("Erro ao salvar perfil", e, profile);
            }
        }

        function formatarSerie(serie) {
            const series = {
                EF1: "1º ano",
                EF2: "2º ano",
                EF3: "3º ano",
                EF4: "4º ano",
                EF5: "5º ano",
                EF6: "6º ano",
                EF7: "7º ano",
                EF8: "8º ano",
                EF9: "9º ano",
                EM1: "1º ano EM",
                EM2: "2º ano EM",
                EM3: "3º ano EM"
            };

            return series[serie] || serie || "-";
        }

        async function loadProfile() {
            try {
                const profile = await fetchJson(`${API}/usuario`, {}, "carregar perfil");
                if (!profile) return;

                if (profile.tipo && tipoSelect) tipoSelect.value = profile.tipo;
                if (profile.tipo === 'professor') {
                    if (professorInput) {
                        professorInput.value = profile.nome || '';
                        professorField.classList.remove('hidden');
                    }
                } else {
                    if (professorInput) professorInput.value = '';
                    if (professorField) professorField.classList.add('hidden');
                }

                if (profile.disciplina_preferida && disciplinaSelect && serieSelect.value) {
                    disciplinaSelect.value = profile.disciplina_preferida;
                    await carregarConteudos(profile.disciplina_preferida);
                }
            } catch (e) {
                registrarErro("Erro ao carregar perfil", e);
            }
        }

        if (tipoSelect) {
            tipoSelect.addEventListener('change', async (e) => {
                if (e.target.value === 'professor') {
                    professorField.classList.remove('hidden');
                } else {
                    professorField.classList.add('hidden');
                    if (professorInput) professorInput.value = '';
                }
                await saveProfile();
            });
        }

        if (professorInput) {
            professorInput.addEventListener('blur', saveProfile);
        }

        carregarDisciplinas().then(() => loadProfile()).catch(() => {});

