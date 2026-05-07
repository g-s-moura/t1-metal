#simulador configuravel
import yaml

# Leitor para aceitar o !PARAMETERS do arquivo .yml do professor
class ParametersLoader(yaml.SafeLoader):
    pass

def parameters_constructor(loader, node):
    return loader.construct_mapping(node, deep=True)

ParametersLoader.add_constructor("!PARAMETERS", parameters_constructor)

# PARÂMETROS
pA = 1664525   # Multiplicador
pC = 1013904223 # Incremento
pM = 2**32 # Módulo
seed = 1
numbers_gen = 0 # número de números gerados
n_max = 100000 # número máximo a ser gerado
rndnumbers = [] # lista de números aleatórios informada no yml
usar_rndnumbers = False # indica se vamos usar a lista fixa ou o gerador automático

def next_random():
    """Gera o próximo número pseudoaleatório entre 0 e 1."""
    global seed, numbers_gen, n_max, rndnumbers, usar_rndnumbers

    if numbers_gen >= n_max:
        return None # chegamos ao máximo

    # Se o yml tiver uma lista fixa de aleatórios, usa ela
    if usar_rndnumbers:
        valor = rndnumbers[numbers_gen]
        numbers_gen += 1 # Indica que já usamos um número
        return valor

    # Caso contrário, gera pelo método congruente linear
    seed = ((pA * seed) + pC) % pM
    numbers_gen += 1 # Indica que já geramos um número
    return seed / pM # Normaliza entre 0 e 1

#Simulação

def simular_rede(modelo):
    global seed, numbers_gen, n_max, rndnumbers, usar_rndnumbers
        
    with open(modelo, 'r', encoding='utf-8') as file:
        config = yaml.load(file, Loader=ParametersLoader) #que é o arquivo yaml, no caso, ele ta programado com as instruções do sistema da imagem

    # Resetando para a simulação
    # Se tiver seeds no yml, usamos o gerador automático
    # Se não tiver seeds, mas tiver rndnumbers, usamos a lista fixa de aleatórios
    numbers_gen = 0

    if 'seeds' in config:
        seed = config.get('seeds', [1])[0]
        n_max = config.get('rndnumbersPerSeed', 100000)
        rndnumbers = []
        usar_rndnumbers = False

    elif 'rndnumbers' in config:
        rndnumbers = config['rndnumbers']
        n_max = len(rndnumbers)
        usar_rndnumbers = True

    else:
        seed = 1
        n_max = 100000
        rndnumbers = []
        usar_rndnumbers = False
        
    filas = config['queues']

    # Prepara as chegadas externas
    # Aceita o formato do professor:
    # arrivals:
    #   Q1: 2.0
    chegadas = []

    if isinstance(config['arrivals'], dict):
        for fila, tempo in config['arrivals'].items():
            chegadas.append({
                'queue': fila,
                'time': tempo
            })
    else:
        chegadas = config['arrivals']

    # Prepara o roteamento
    # Aceita o formato do professor com network
    roteamento = {q: {} for q in filas}

    if 'network' in config:
        for rota in config['network']:
            origem = rota['source']
            destino = rota['target']
            prob = rota['probability']
            roteamento[origem][destino] = prob
    else:
        roteamento = config.get('routing', {})

    # Se alguma fila não tiver 100% das rotas explícitas,
    # o restante é considerado saída para fora do sistema.
    # Se a fila não tiver rota nenhuma, ela sai para OUT sem gastar aleatório.
    for q in filas:
        soma = sum(roteamento.get(q, {}).values())

        if soma == 0:
            pass
        elif soma < 1.0:
            roteamento[q]['OUT'] = roteamento[q].get('OUT', 0.0) + (1.0 - soma)
    
    # Variáveis de estado inicial das filas
    estado_atual = {q: 0 for q in filas}
    tempo_global = 0.0
    ultimo_tempo_evento = 0.0
    
    clientes_perdidos = {q: 0 for q in filas}
    
    tempos_estados = {q: {} for q in filas}
    
    eventos = [] #lista para anotar os eventos ocorridos. Formato: (tempo, tipo_evento, fila_alvo)
    
    for chegada in chegadas:
        eventos.append((chegada.get('time', 2.0), 'CHEGADA_EXTERNA', chegada['queue'], 'OUT')) # Primeiro cliente chegando no tempo indicado no yml
        
    def escolher_destino(fila):
        """Escolhe o destino do cliente após ser atendido em uma fila."""

        probabilidades = roteamento.get(fila, {}) #roteamento do yaml

        # Se não existe rota configurada, o cliente sai do sistema
        if not probabilidades:
            return 'OUT'

        rnd = next_random()
        if rnd is None:
            return None

        soma_acumulada = 0.0
        destino = 'OUT'
        
        for dest, prob in probabilidades.items():
            soma_acumulada += prob
            if rnd <= soma_acumulada:
                destino = dest
                break

        return destino

    def agendar_saida(fila, tempo):
        """Agenda o fim do atendimento de um cliente em uma fila."""

        # Primeiro sorteia para onde o cliente vai depois do atendimento
        destino = escolher_destino(fila)

        if destino is None:
            return False

        min_s = filas[fila].get('min_service', filas[fila].get('minService'))
        max_s = filas[fila].get('max_service', filas[fila].get('maxService'))

        # Depois sorteia o tempo de serviço
        rnd = next_random()

        if rnd is None:
            return False

        t_serv = min_s + (max_s - min_s) * rnd

        eventos.append((tempo + t_serv, 'SAIDA', fila, destino))

        return True

    def tratar_chegada(fila, tempo):
        """Processa a entrada de um cliente em uma fila."""
        cap = filas[fila].get('capacity', float('inf'))
        servs = filas[fila]['servers']
        
        if estado_atual[fila] < cap:
            estado_atual[fila] += 1

            if estado_atual[fila] <= servs: # Tem servidor livre
                if not agendar_saida(fila, tempo):
                    return False

        else:
            clientes_perdidos[fila] += 1

        return True

    # LOOP principal
    while eventos and numbers_gen < n_max:
        eventos.sort()  #arruma a lista cronologica
        tempo_atual, tipo_evento, fila, destino = eventos.pop(0)
        
        var_tempo = tempo_atual - ultimo_tempo_evento
        for q in filas:
            est = estado_atual[q]
            if est not in tempos_estados[q]:
                tempos_estados[q][est] = 0.0
            tempos_estados[q][est] += var_tempo
            
        tempo_global = tempo_atual
        ultimo_tempo_evento = tempo_atual
        
        if tipo_evento == 'CHEGADA_EXTERNA':
            if not tratar_chegada(fila, tempo_atual): break
            
            # Agenda a próxima chegada externa
            min_c = filas[fila].get('min_arrival', filas[fila].get('minArrival'))
            max_c = filas[fila].get('max_arrival', filas[fila].get('maxArrival'))

            # Caso o yml esteja no formato antigo, pega min e max da chegada
            if min_c is None or max_c is None:
                cfg_chegada = next((c for c in chegadas if c['queue'] == fila), None)

                if cfg_chegada is not None:
                    min_c = cfg_chegada.get('min')
                    max_c = cfg_chegada.get('max')

            if min_c is not None and max_c is not None:
                rnd = next_random()
                if rnd is None: break
                t_chegada = min_c + (max_c - min_c) * rnd
                eventos.append((tempo_atual + t_chegada, 'CHEGADA_EXTERNA', fila, 'OUT'))
            
        elif tipo_evento == 'SAIDA':
            estado_atual[fila] -= 1
            servs = filas[fila]['servers']
            
            # Se tem alguém na fila de espera, vai para o funcionário que acabou de liberar
            if estado_atual[fila] >= servs:
                if not agendar_saida(fila, tempo_atual):
                    break
        
            if destino != 'OUT':
                if not tratar_chegada(destino, tempo_atual): break  # Se o destino não for OUT, o cliente entra na nova fila
                    
        # resultados
    print(f"RESULTADOS DA SIMULAÇÃO")
    print(f"Tempo Global de Simulação: {tempo_global:.4f}")
    print(f"Números Aleatórios Gerados: {numbers_gen}")

    total_perdidos = sum(clientes_perdidos.values())
    print(f"Total de Clientes Perdidos: {total_perdidos}")
    
    for q in filas:
        print()
        print(f"Resultado da fila {q}")
        print(f"Clientes Perdidos na fila {q}: {clientes_perdidos[q]}")
        
        # Se a fila tem capacidade definida, mostra todos os estados até a capacidade.
        # Se não tem capacidade, mostra até o maior estado observado.
        cap = filas[q].get('capacity', None)

        if cap is None:
            maior_estado = max(tempos_estados[q].keys()) if tempos_estados[q] else 0
        else:
            maior_estado = int(cap)

        for est in range(0, maior_estado + 1):
            tempo_acumulado = tempos_estados[q].get(est, 0.0)
            probabilidade = (tempo_acumulado / tempo_global) * 100 if tempo_global > 0 else 0
            print(f"{est:>2} clientes: Tempo = {tempo_acumulado:.4f} | Prob = {probabilidade:.4f}%")

# Execusão
simular_rede('modelo.yml')