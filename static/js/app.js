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
        const trocaQuestaoModal = document.getElementById("trocaQuestaoModal");
        const trocaQuestaoResumo = document.getElementById("trocaQuestaoResumo");
        const trocaQuestaoFechar = document.getElementById("trocaQuestaoFechar");
        const trocaQuestaoCriar = document.getElementById("trocaQuestaoCriar");
        const trocaTipoButtons = document.querySelectorAll(".troca-tipo");
        const novaQuestaoModal = document.getElementById("novaQuestaoModal");
        const novaQuestaoResumo = document.getElementById("novaQuestaoResumo");
        const novaQuestaoForm = document.getElementById("novaQuestaoForm");
        const novaQuestaoFechar = document.getElementById("novaQuestaoFechar");
        const novaQuestaoCancelar = document.getElementById("novaQuestaoCancelar");
        const novaQuestaoTipo = document.getElementById("novaQuestaoTipo");
        const novaQuestaoDificuldade = document.getElementById("novaQuestaoDificuldade");
        const novaQuestaoConteudo = document.getElementById("novaQuestaoConteudo");
        const novaQuestaoEnunciado = document.getElementById("novaQuestaoEnunciado");
        const novaQuestaoAlternativas = document.getElementById("novaQuestaoAlternativas");
        const novaQuestaoGabarito = document.getElementById("novaQuestaoGabarito");
        const novaQuestaoErro = document.getElementById("novaQuestaoErro");
        const novaQuestaoSalvar = document.getElementById("novaQuestaoSalvar");
        const novaAlternativas = document.querySelectorAll(".nova-alternativa");
        const editarQuestaoModal = document.getElementById("editarQuestaoModal");
        const editarQuestaoResumo = document.getElementById("editarQuestaoResumo");
        const editarQuestaoForm = document.getElementById("editarQuestaoForm");
        const editarQuestaoFechar = document.getElementById("editarQuestaoFechar");
        const editarQuestaoCancelar = document.getElementById("editarQuestaoCancelar");
        const editarQuestaoEnunciado = document.getElementById("editarQuestaoEnunciado");
        const editarQuestaoLinhasGrupo = document.getElementById("editarQuestaoLinhasGrupo");
        const editarQuestaoLinhas = document.getElementById("editarQuestaoLinhas");
        const editarQuestaoErro = document.getElementById("editarQuestaoErro");
        const editarQuestaoSalvar = document.getElementById("editarQuestaoSalvar");

        let conteudosDisponiveis = [];
        let conteudosArvore = [];
        let conteudosSelecionados = new Set();
        let conteudosExpandidos = new Set();
        let previewAtual = null;
        let trocaQuestaoId = null;
        let novaQuestaoSubstituirId = null;
        let editarQuestaoId = null;
        let previewFeedback = null;
        let previewHighlightId = null;
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
            if (response.status === 401) {
                window.location.href = '/';
                throw new Error('Sua sessão expirou.');
            }
            if (!response.ok) {
                const body = await response.text();
                throw new Error(body || `${contexto} falhou (${response.status})`);
            }

            return response.json();
        }

        async function fetchBlob(url, options = {}, contexto = "download") {
            const response = await fetch(url, options);
            if (response.status === 401) {
                window.location.href = '/';
                throw new Error('Sua sessão expirou.');
            }
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
            fecharTrocaQuestaoModal();
            fecharNovaQuestaoModal();
            fecharEditarQuestaoModal();
            document.body.classList.remove("overflow-hidden");
        }

        function abrirTrocaQuestaoModal(questao) {
            trocaQuestaoId = questao.id;
            trocaQuestaoResumo.textContent = `Questão ${questao.numero}: escolha o tipo da nova questão.`;
            trocaQuestaoModal.classList.remove("hidden");
        }

        function fecharTrocaQuestaoModal() {
            trocaQuestaoId = null;
            trocaQuestaoModal.classList.add("hidden");
        }

        function abrirNovaQuestaoModal(opcoes = {}) {
            novaQuestaoForm.reset();
            novaQuestaoErro.classList.add("hidden");
            novaQuestaoErro.textContent = "";
            novaQuestaoSubstituirId = opcoes.substituirId || null;
            novaQuestaoResumo.textContent = novaQuestaoSubstituirId
                ? `A nova questão substituirá a questão ${opcoes.numero || ""} nesta prévia.`
                : "A questão será adicionada apenas nesta prévia.";
            novaQuestaoSalvar.innerHTML = novaQuestaoSubstituirId
                ? '<i class="fas fa-sync-alt"></i> Substituir'
                : '<i class="fas fa-plus"></i> Adicionar';
            novaQuestaoTipo.value = (previewAtual && previewAtual.meta && previewAtual.meta.tipo) || "objetiva";
            novaQuestaoDificuldade.value = (previewAtual && previewAtual.meta && previewAtual.meta.dificuldade) || "Manual";
            alternarCamposNovaQuestao();
            fecharTrocaQuestaoModal();
            novaQuestaoModal.classList.remove("hidden");
            novaQuestaoEnunciado.focus();
        }

        function fecharNovaQuestaoModal() {
            novaQuestaoSubstituirId = null;
            novaQuestaoModal.classList.add("hidden");
        }

        function abrirEditarQuestaoModal(questao) {
            editarQuestaoId = questao.id;
            editarQuestaoResumo.textContent = `Editando a questão ${questao.numero}.`;
            editarQuestaoEnunciado.value = questao.enunciado || "";
            editarQuestaoLinhas.value = questao.linhas_resposta || 3;
            editarQuestaoLinhasGrupo.classList.toggle("hidden", !!(questao.alternativas || []).length);
            editarQuestaoErro.classList.add("hidden");
            editarQuestaoErro.textContent = "";
            editarQuestaoModal.classList.remove("hidden");
            editarQuestaoEnunciado.focus();
        }

        function fecharEditarQuestaoModal() {
            editarQuestaoId = null;
            editarQuestaoModal.classList.add("hidden");
        }

        function mostrarErroEditarQuestao(mensagem) {
            editarQuestaoErro.textContent = mensagem;
            editarQuestaoErro.classList.remove("hidden");
        }

        function alternarCamposNovaQuestao() {
            const objetiva = novaQuestaoTipo.value === "objetiva";
            novaQuestaoAlternativas.classList.toggle("hidden", !objetiva);
            novaAlternativas.forEach((input, index) => {
                input.required = objetiva && index < 2;
            });
            novaQuestaoGabarito.required = objetiva;
        }

        function mostrarErroNovaQuestao(mensagem) {
            novaQuestaoErro.textContent = mensagem;
            novaQuestaoErro.classList.remove("hidden");
        }

        function montarPayloadNovaQuestao() {
            const tipo = novaQuestaoTipo.value;
            const alternativas = Array.from(novaAlternativas)
                .map((input) => input.value.trim())
                .filter(Boolean);

            return {
                preview_id: previewAtual.preview_id,
                questao_id: novaQuestaoSubstituirId,
                tipo,
                enunciado: novaQuestaoEnunciado.value.trim(),
                alternativas: tipo === "objetiva" ? alternativas : [],
                gabarito: tipo === "objetiva" ? novaQuestaoGabarito.value : null,
                conteudo: novaQuestaoConteudo.value.trim() || null,
                dificuldade: novaQuestaoDificuldade.value || null
            };
        }

        function definirFeedbackPreview(mensagem, tipo = "success") {
            previewFeedback = { mensagem, tipo };
            window.setTimeout(() => {
                if (previewFeedback && previewFeedback.mensagem === mensagem) {
                    previewFeedback = null;
                    if (previewAtual && !previewModal.classList.contains("hidden")) {
                        renderizarPreview(previewAtual);
                    }
                }
            }, 3200);
        }

        function statCard(valor, rotulo) {
            return `
                <div class="summary-stat">
                    <strong>${escapeHtml(valor)}</strong>
                    <span>${escapeHtml(rotulo)}</span>
                </div>
            `;
        }

        function badgeQuestao(valor, icone = "fa-tag", extraClasse = "") {
            if (!valor) return "";
            return `
                <span class="question-badge ${extraClasse}">
                    <i class="fas ${icone}"></i>
                    <span>${escapeHtml(valor)}</span>
                </span>
            `;
        }

        function separarCreditosImagemTexto(texto) {
            const creditos = [];
            const regex = /Dispon.vel\s+em\s*:\s*[\s\S]*?Acesso\s+em\s*:\s*\d{1,2}\s+[^\s.]+\.?\s+\d{4}\.?/gi;
            const enunciado = String(texto || "").replace(regex, (match) => {
                creditos.push(match.replace(/\s+/g, " ").trim());
                return " ";
            }).replace(/[ \t]{2,}/g, " ").replace(/\n{3,}/g, "\n\n").trim();

            return { enunciado, creditos };
        }

        function encontrarCardQuestao(questaoId) {
            return Array.from(previewQuestoes.querySelectorAll(".question-card"))
                .find((card) => String(card.dataset.questaoId) === String(questaoId));
        }

        function marcarCardCarregando(questaoId, mensagem, seletor = ".trocar-questao") {
            const card = encontrarCardQuestao(questaoId);
            if (!card) return;

            card.classList.add("is-loading");
            const botao = card.querySelector(seletor);
            if (botao && mensagem) {
                botao.innerHTML = `<i class="fas fa-spinner fa-spin"></i><span>${escapeHtml(mensagem)}</span>`;
            }
        }

        function renderizarPreview(data) {
            previewAtual = data;
            abrirPreviewModal();

            const stats = data.estatisticas || {};
            const dificuldades = Object.entries(stats.dificuldades || {});
            const dificuldadesHtml = dificuldades.length
                ? dificuldades
                    .map(([nome, total]) => `
                        <div class="summary-row">
                            <span>${escapeHtml(nome)}</span>
                            <b>${total}</b>
                        </div>
                    `)
                    .join("")
                : "<span class='text-sm text-slate-500'>Sem dados</span>";

            const quantidadeSolicitada = data.quantidade_solicitada || (data.meta && data.meta.quantidade) || data.quantidade;
            const faltantes = Math.max(quantidadeSolicitada - data.quantidade, 0);
            const avisos = data.avisos || [];
            const avisosHtml = avisos
                .map((aviso) => `
                    <div class="preview-notice">
                        <div class="font-bold"><i class="fas fa-triangle-exclamation mr-2"></i>Atenção</div>
                        <div class="mt-1">${escapeHtml(aviso.mensagem || "")}</div>
                    </div>
                `)
                .join("");
            const feedbackHtml = previewFeedback ? `
                <div class="preview-notice ${previewFeedback.tipo === "success" ? "success" : ""}">
                    <div class="font-bold"><i class="fas fa-check-circle mr-2"></i>${escapeHtml(previewFeedback.mensagem)}</div>
                </div>
            ` : "";
            const criarQuestaoHtml = faltantes > 0 ? `
                <div class="preview-notice success">
                    <div class="font-bold"><i class="fas fa-plus-circle mr-2"></i>Completar avaliação</div>
                    <div class="mt-1 text-emerald-800">Faltam ${faltantes} questão${faltantes > 1 ? "ões" : ""} para chegar ao total solicitado.</div>
                    <button type="button" class="criar-questao-manual preview-mini-action">
                        <i class="fas fa-plus"></i>
                        Criar questão
                    </button>
                </div>
            ` : "";

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
                ${feedbackHtml}
                ${avisosHtml}
                ${criarQuestaoHtml}
                <div class="summary-panel">
                    <div class="summary-title"><i class="fas fa-chart-simple text-blue-600"></i>Resumo</div>
                    <div class="summary-grid">
                        ${statCard(data.quantidade, `de ${quantidadeSolicitada} questões`)}
                        ${statCard(data.reservas || 0, "reservas")}
                    </div>
                </div>
                <div class="summary-panel">
                    <div class="summary-title"><i class="fas fa-layer-group text-blue-600"></i>Tipos de questão</div>
                    <div class="summary-grid">
                        ${statCard(stats.objetivas || 0, "objetivas")}
                        ${statCard(stats.discursivas || 0, "discursivas")}
                    </div>
                </div>
                <div class="summary-panel">
                    <div class="summary-title"><i class="fas fa-signal text-blue-600"></i>Dificuldades</div>
                    <div class="summary-list">${dificuldadesHtml}</div>
                </div>
                <div class="summary-panel">
                    <div class="summary-title"><i class="fas fa-image text-blue-600"></i>Imagens</div>
                    <div class="summary-grid">
                        ${statCard(stats.com_imagem || 0, "com imagem")}
                    </div>
                </div>
            `;
            const criarQuestaoButton = previewStats.querySelector(".criar-questao-manual");
            if (criarQuestaoButton) {
                criarQuestaoButton.addEventListener("click", abrirNovaQuestaoModal);
            }

            previewQuestoes.innerHTML = "";

            if (!data.questoes || !data.questoes.length) {
                previewQuestoes.innerHTML = `
                    <div class="empty-preview">
                        <div class="text-3xl text-amber-500 mb-3"><i class="fas fa-circle-info"></i></div>
                        <div class="text-lg font-bold text-slate-900">Nenhuma questão encontrada</div>
                        <div class="mt-2 text-sm">Ajuste a série, disciplina, conteúdo ou dificuldade para montar uma nova prévia.</div>
                    </div>`;
                return;
            }

            data.questoes.forEach((questao) => {
                const card = document.createElement("article");
                card.className = `question-card ${String(previewHighlightId) === String(questao.id) ? "is-updated" : ""}`;
                card.dataset.questaoId = questao.id;
                const textoQuestao = separarCreditosImagemTexto(questao.enunciado || "");
                const creditosDaQuestao = [
                    ...(questao.creditos_imagem || []),
                    ...textoQuestao.creditos
                ].filter((credito, index, lista) => credito && lista.indexOf(credito) === index);

                const alternativas = (questao.alternativas || [])
                    .map((alt) => `<div class="alternative-item">${escapeHtml(alt)}</div>`)
                    .join("");

                const creditosImagem = creditosDaQuestao
                    .map((credito) => `<div class="image-credit">${escapeHtml(credito)}</div>`)
                    .join("");

                const imagens = (questao.imagens || [])
                    .map((src) => `
                        <figure class="question-media">
                            <img src="${escapeHtml(src)}" alt="Imagem da questão ${escapeHtml(questao.numero)}">
                            ${creditosImagem}
                        </figure>
                    `)
                    .join("");

                const badges = [
                    badgeQuestao(questao.tipo, questao.tipo === "objetiva" ? "fa-list-ul" : "fa-pen-to-square"),
                    badgeQuestao(questao.dificuldade, "fa-signal", "neutral"),
                    badgeQuestao(data.disciplina, "fa-book", "neutral"),
                    badgeQuestao(questao.conteudo, "fa-folder-tree", "neutral"),
                    badgeQuestao(questao.origem, "fa-route", "neutral")
                ].join("");
                const linhasResposta = Math.max(1, Math.min(Number(questao.linhas_resposta || 3), 12));
                const linhasRespostaHtml = Array.from({ length: linhasResposta })
                    .map(() => '<div class="answer-line"></div>')
                    .join("");

                card.innerHTML = `
                    <div class="question-topline">
                        <div class="question-badges">${badges}</div>
                        <div class="question-actions">
                            <button type="button" class="editar-questao question-action edit" aria-label="Editar questão ${escapeHtml(questao.numero)}">
                                <i class="fas fa-pen"></i>
                                <span>Editar</span>
                            </button>
                            <button type="button" class="trocar-questao question-action swap" aria-label="Trocar questão ${escapeHtml(questao.numero)}">
                                <i class="fas fa-sync-alt"></i>
                                <span>Trocar</span>
                            </button>
                            <button type="button" class="remover-questao question-action remove" aria-label="Remover questão ${escapeHtml(questao.numero)}">
                                <i class="fas fa-trash"></i>
                                <span>Remover</span>
                            </button>
                        </div>
                    </div>
                    <div class="question-body">
                        <div class="question-number">${escapeHtml(questao.numero)}</div>
                        <div class="question-enunciado">${escapeHtml(textoQuestao.enunciado || "")}</div>
                    </div>
                    ${imagens}
                    ${alternativas ? `<div class="alternatives-list">${alternativas}</div>` : ""}
                    ${questao.tipo === "discursiva" ? `
                        <div class="answer-lines">
                            ${linhasRespostaHtml}
                        </div>
                    ` : ""}
                `;

                card.querySelector(".editar-questao").addEventListener("click", () => abrirEditarQuestaoModal(questao));
                card.querySelector(".trocar-questao").addEventListener("click", () => abrirTrocaQuestaoModal(questao));
                card.querySelector(".remover-questao").addEventListener("click", () => removerQuestaoPreview(questao.id));
                previewQuestoes.appendChild(card);
            });

            if (previewHighlightId) {
                window.setTimeout(() => {
                    previewHighlightId = null;
                    document.querySelectorAll(".question-card.is-updated")
                        .forEach((item) => item.classList.remove("is-updated"));
                }, 1600);
            }
        }

        async function trocarQuestaoPreview(questaoId, tipo) {
            if (!previewAtual) return;

            const questaoAnterior = (previewAtual.questoes || []).find(
                (questao) => String(questao.id) === String(questaoId)
            );
            marcarCardCarregando(questaoId, "Trocando...");

            try {
                fecharTrocaQuestaoModal();
                previewResumo.textContent = `Trocando por questão ${tipo}...`;
                const data = await fetchJson(`${API}/previsualizar-atividade/trocar`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        preview_id: previewAtual.preview_id,
                        questao_id: questaoId,
                        tipo
                    })
                }, "trocar questão");

                const questaoNova = questaoAnterior
                    ? (data.questoes || []).find((questao) => questao.numero === questaoAnterior.numero)
                    : null;
                previewHighlightId = questaoNova ? questaoNova.id : null;
                definirFeedbackPreview("Questão trocada com sucesso.");
                renderizarPreview(data);
            } catch (erro) {
                registrarErro("Erro ao trocar questão da prévia", erro, { questaoId });
                alert(textoErro(erro, "Não consegui trocar essa questão. Talvez não haja reserva compatível."));
                renderizarPreview(previewAtual);
            }
        }

        async function removerQuestaoPreview(questaoId) {
            if (!previewAtual) return;
            const confirma = window.confirm("Remover esta questão da prévia?");
            if (!confirma) return;

            try {
                marcarCardCarregando(questaoId, "Removendo...", ".remover-questao");
                const data = await fetchJson(`${API}/previsualizar-atividade/remover`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ preview_id: previewAtual.preview_id, questao_id: questaoId })
                }, "remover questão");

                definirFeedbackPreview("Questão removida da prévia.");
                renderizarPreview(data);
            } catch (erro) {
                registrarErro("Erro ao remover questão da prévia", erro, { questaoId });
                alert(textoErro(erro, "Não consegui remover essa questão."));
                renderizarPreview(previewAtual);
            }
        }

        async function adicionarQuestaoManual(event) {
            event.preventDefault();
            if (!previewAtual) return;

            const payload = montarPayloadNovaQuestao();
            if (!payload.enunciado) {
                mostrarErroNovaQuestao("Informe o enunciado da questão.");
                return;
            }

            if (payload.tipo === "objetiva") {
                if (payload.alternativas.length < 2) {
                    mostrarErroNovaQuestao("Informe pelo menos duas alternativas.");
                    return;
                }

                if (!payload.gabarito) {
                    mostrarErroNovaQuestao("Escolha o gabarito da questão objetiva.");
                    return;
                }
            }

            novaQuestaoSalvar.disabled = true;
            novaQuestaoSalvar.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Adicionando...';
            novaQuestaoErro.classList.add("hidden");

            try {
                const data = await fetchJson(`${API}/previsualizar-atividade/adicionar`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                }, "adicionar questão manual");

                const questoesRetorno = data.questoes || [];
                const numeroSubstituido = (previewAtual.questoes || [])
                    .find((item) => String(item.id) === String(payload.questao_id))?.numero;
                const questaoManual = payload.questao_id
                    ? questoesRetorno.find((questao) => String(questao.numero) === String(numeroSubstituido))
                    : questoesRetorno[questoesRetorno.length - 1];
                previewHighlightId = questaoManual ? questaoManual.id : null;
                definirFeedbackPreview(payload.questao_id ? "Questão substituída com sucesso." : "Questão adicionada à prévia.");
                fecharNovaQuestaoModal();
                renderizarPreview(data);
            } catch (erro) {
                registrarErro("Erro ao adicionar questão manual", erro, payload);
                mostrarErroNovaQuestao(textoErro(erro, "Não consegui adicionar essa questão."));
            } finally {
                novaQuestaoSalvar.disabled = false;
                novaQuestaoSalvar.innerHTML = novaQuestaoSubstituirId
                    ? '<i class="fas fa-sync-alt"></i> Substituir'
                    : '<i class="fas fa-plus"></i> Adicionar';
            }
        }

        async function salvarEdicaoQuestao(event) {
            event.preventDefault();
            if (!previewAtual || !editarQuestaoId) return;

            const questaoAtual = (previewAtual.questoes || []).find(
                (questao) => String(questao.id) === String(editarQuestaoId)
            );
            const enunciado = editarQuestaoEnunciado.value.trim();
            if (!enunciado) {
                mostrarErroEditarQuestao("Informe o enunciado da questão.");
                return;
            }

            const payload = {
                preview_id: previewAtual.preview_id,
                questao_id: editarQuestaoId,
                enunciado,
                linhas_resposta: questaoAtual && !(questaoAtual.alternativas || []).length
                    ? Number(editarQuestaoLinhas.value || 3)
                    : null
            };

            editarQuestaoSalvar.disabled = true;
            editarQuestaoSalvar.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Salvando...';
            editarQuestaoErro.classList.add("hidden");

            try {
                const data = await fetchJson(`${API}/previsualizar-atividade/editar`, {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                }, "editar questão");

                previewHighlightId = editarQuestaoId;
                definirFeedbackPreview("Questão editada com sucesso.");
                fecharEditarQuestaoModal();
                renderizarPreview(data);
            } catch (erro) {
                registrarErro("Erro ao editar questão", erro, payload);
                mostrarErroEditarQuestao(textoErro(erro, "Não consegui salvar a edição."));
            } finally {
                editarQuestaoSalvar.disabled = false;
                editarQuestaoSalvar.innerHTML = '<i class="fas fa-save"></i> Salvar edição';
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
        trocaQuestaoFechar.addEventListener("click", fecharTrocaQuestaoModal);
        trocaQuestaoModal.addEventListener("click", (event) => {
            if (!event.target.closest || !event.target.closest(".max-w-md")) fecharTrocaQuestaoModal();
        });
        trocaTipoButtons.forEach((button) => {
            button.addEventListener("click", () => {
                if (!trocaQuestaoId) return;
                trocarQuestaoPreview(trocaQuestaoId, button.dataset.tipo);
            });
        });
        trocaQuestaoCriar.addEventListener("click", () => {
            if (!trocaQuestaoId || !previewAtual) return;
            const questao = (previewAtual.questoes || []).find(
                (item) => String(item.id) === String(trocaQuestaoId)
            );
            abrirNovaQuestaoModal({
                substituirId: trocaQuestaoId,
                numero: questao ? questao.numero : ""
            });
        });
        novaQuestaoFechar.addEventListener("click", fecharNovaQuestaoModal);
        novaQuestaoCancelar.addEventListener("click", fecharNovaQuestaoModal);
        novaQuestaoTipo.addEventListener("change", alternarCamposNovaQuestao);
        novaQuestaoForm.addEventListener("submit", adicionarQuestaoManual);
        novaQuestaoModal.addEventListener("click", (event) => {
            if (!event.target.closest || !event.target.closest(".max-w-2xl")) fecharNovaQuestaoModal();
        });
        editarQuestaoFechar.addEventListener("click", fecharEditarQuestaoModal);
        editarQuestaoCancelar.addEventListener("click", fecharEditarQuestaoModal);
        editarQuestaoForm.addEventListener("submit", salvarEdicaoQuestao);
        editarQuestaoModal.addEventListener("click", (event) => {
            if (!event.target.closest || !event.target.closest(".max-w-2xl")) fecharEditarQuestaoModal();
        });

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

                const headerName = document.getElementById('headerUserName');
                const userInitial = document.getElementById('userInitial');
                if (headerName) headerName.textContent = profile.nome || profile.email || 'Usuário';
                if (userInitial) userInitial.textContent = (profile.nome || profile.email || 'U').trim().charAt(0).toUpperCase();

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

        const logoutButton = document.getElementById('logoutButton');
        if (logoutButton) {
            logoutButton.addEventListener('click', async () => {
                await fetch(`${API}/auth/logout`, { method: 'POST' });
                window.location.href = '/';
            });
        }

        carregarDisciplinas().then(() => loadProfile()).catch(() => {});

