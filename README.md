# Temakeria — Gastronomia Japonesa

Landing page responsiva da Temakeria, com paleta azul-marinho e dourado.

## Site

Endereço esperado após a publicação do GitHub Pages:
https://fernandohsmarques04.github.io/temakeria-/

O workflow `.github/workflows/pages.yml` prepara a implantação automaticamente a cada push em `main`. Consulte **Actions** para verificar se o deploy foi concluído. Caso necessário, entre em **Settings > Pages > Build and deployment** e selecione **GitHub Actions**.

## Fotografias originais

Para que o site exiba as fotos originais, envie a pasta `assets/` do pacote entregue no ChatGPT para a raiz deste repositório, mantendo os nomes:

- combinado-chef.webp
- combinado-tradicional.webp
- poke-camarao.webp
- sushi-copo.webp
- especiais.webp
- poke-salmao.webp
- niguiris.webp
- chef.webp
- logo.webp

Até os arquivos serem enviados, o site utiliza imagens externas ilustrativas como substitutas e não deve ser apresentado como versão final com fotos originais.

## Dados comerciais

Instagram, WhatsApp, horários, endereço completo, preços e ingredientes específicos precisam ser confirmados antes da divulgação final.

## Cardápio e painel no PC

A página institucional continua em `index.html`. O servidor local abre o
cardápio em `/cardapio` e também oferece a página institucional em
`/institucional`. O painel permite cadastrar e editar categorias e produtos,
enviar ou remover fotos, definir preços e controlar a presença no cardápio.
Ocultar uma categoria retira todos os seus produtos da página pública.

### Instalação no Windows

Instale o Python 3.11 ou mais recente. No PowerShell, dentro do repositório:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m temakeria init-admin
.\.venv\Scripts\python.exe -m temakeria serve
```

No Linux ou macOS, use `python3 -m venv .venv` e substitua
`.\.venv\Scripts\python.exe` por `.venv/bin/python` nos demais comandos.

- Painel no PC em <http://127.0.0.1:8081/admin>.
- Cardápio no PC em <http://127.0.0.1:8080/cardapio>.
- Para trocar a senha, pare o servidor com Ctrl+C, rode `init-admin` e
  inicie o servidor novamente. Isso encerra as sessões anteriores.

A primeira inicialização importa as categorias, os nomes e as fotos da
galeria. A **Surpresa do Cheff** vem com o valor inicial de **R$ 150,00** já
divulgado na página institucional. Os demais pratos entram como
indisponíveis e sem preço. Confira o catálogo no painel antes de imprimir o QR.

O catálogo, as fotos enviadas e a credencial do painel ficam no SQLite em
`data/temakeria.sqlite3`. As fotos enviadas são redimensionadas e salvas junto
com os dados do produto. Para fazer backup ou restaurar os dados, encerre o
servidor e copie toda a pasta `data/`. Mantenha o PC e o servidor ligados
enquanto o cardápio estiver em uso.

### Acesso pelo Wi-Fi

1. Com o PC ligado à rede do restaurante, rode `ipconfig` e identifique o
   endereço IPv4 do adaptador conectado. Reserve esse endereço no roteador
   se for imprimir um QR para uso na rede local.
2. Libere a porta TCP **8080** no Firewall do Windows para o perfil privado e a
   rede local. Se a rede de visitantes isolar os dispositivos do PC, use o
   endereço público descrito abaixo.
3. Inicie o servidor com o endereço real do PC. Exemplo para `192.168.1.50`:

   ```powershell
   .\.venv\Scripts\python.exe -m temakeria serve --menu-url http://192.168.1.50:8080/cardapio
   ```

4. No painel, baixe o QR Code. Escaneie com um celular conectado ao Wi-Fi.

### Um QR para Wi-Fi e dados móveis

Use um endereço público HTTPS estável ligado ao PC por um túnel. Com um
Cloudflare Tunnel nomeado, por exemplo, instale o `cloudflared` no PC,
crie o túnel no painel da Cloudflare e associe um hostname de um domínio
gerenciado nessa conta. Configure o serviço de origem como
`http://127.0.0.1:8080`. Essa porta serve somente o cardápio, as fotos e a
página institucional. O painel atende exclusivamente em `127.0.0.1:8081`.

Com o túnel ativo, inicie o servidor com o hostname real:

```powershell
.\.venv\Scripts\python.exe -m temakeria serve --menu-url https://cardapio.seudominio.com.br
```

O painel gera o PNG com a URL completa do cardápio. Para imprimir um único
QR, teste esse endereço em um celular no Wi-Fi e depois com o Wi-Fi desligado.
O banco permanece no PC. GitHub Pages e Netlify continuam servindo a página
institucional estática e não executam o servidor local.
