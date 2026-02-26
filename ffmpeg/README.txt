FFmpeg 64-bit static Windows build from www.gyan.dev

Version: 7.1.1-essentials_build-www.gyan.dev

License: GPL v3

Source Code: https://github.com/FFmpeg/FFmpeg/commit/db69d06eee

release-essentials build configuration: 

ARCH                      x86 (generic)
big-endian                no
runtime cpu detection     yes
standalone assembly       yes
x86 assembler             nasm
MMX enabled               yes
MMXEXT enabled            yes
3DNow! enabled            yes
3DNow! extended enabled   yes
SSE enabled               yes
SSSE3 enabled             yes
AESNI enabled             yes
AVX enabled               yes
AVX2 enabled              yes
AVX-512 enabled           yes
AVX-512ICL enabled        yes
XOP enabled               yes
FMA3 enabled              yes
FMA4 enabled              yes
i686 features enabled     yes
CMOV is fast              yes
EBX available             yes
EBP available             yes
debug symbols             yes
strip symbols             yes
optimize for size         no
optimizations             yes
static                    yes
shared                    no
postprocessing support    yes
network support           yes
threading support         pthreads
safe bitstream reader     yes
texi2html enabled         no
perl enabled              yes
pod2man enabled           yes
makeinfo enabled          yes
makeinfo supports HTML    yes
xmllint enabled           yes

External libraries:
avisynth                libopencore_amrnb       libvpx
bzlib                   libopencore_amrwb       libwebp
gmp                     libopenjpeg             libx264
gnutls                  libopenmpt              libx265
iconv                   libopus                 libxml2
libaom                  librubberband           libxvid
libass                  libspeex                libzimg
libfontconfig           libsrt                  libzmq
libfreetype             libssh                  lzma
libfribidi              libtheora               mediafoundation
libgme                  libvidstab              sdl2
libgsm                  libvmaf                 zlib
libharfbuzz             libvo_amrwbenc
libmp3lame              libvorbis

External libraries providing hardware acceleration:
amf                     d3d12va                 nvdec
cuda                    dxva2                   nvenc
cuda_llvm               ffnvcodec               vaapi
cuvid                   libmfx
d3d11va                 libvpl

Libraries:
avcodec                 avformat                swresample
avdevice                avutil                  swscale
avfilter                postproc

Programs:
ffmpeg                  ffplay                  ffprobe

Enabled decoders:
aac                     fraps                   pgm
aac_fixed               frwu                    pgmyuv
aac_latm                ftr                     pgssub
aasc                    g2m                     pgx
ac3                     g723_1                  phm
ac3_fixed               g729                    photocd
acelp_kelvin            gdv                     pictor
adpcm_4xm               gem                     pixlet
adpcm_adx               gif                     pjs
adpcm_afc               gremlin_dpcm            png
adpcm_agm               gsm                     ppm
adpcm_aica              gsm_ms                  prores
adpcm_argo              h261                    prosumer
adpcm_ct                h263                    psd
adpcm_dtk               h263i                   ptx
adpcm_ea                h263p                   qcelp
adpcm_ea_maxis_xa       h264                    qdm2
adpcm_ea_r1             h264_cuvid              qdmc
adpcm_ea_r2             h264_qsv                qdraw
adpcm_ea_r3             hap                     qoa
adpcm_ea_xas            hca                     qoi
adpcm_g722              hcom                    qpeg
adpcm_g726              hdr                     qtrle
adpcm_g726le            hevc                    r10k
adpcm_ima_acorn         hevc_cuvid              r210
adpcm_ima_alp           hevc_qsv                ra_144
adpcm_ima_amv           hnm4_video              ra_288
adpcm_ima_apc           hq_hqa                  ralf
adpcm_ima_apm           hqx                     rasc
adpcm_ima_cunning       huffyuv                 rawvideo
adpcm_ima_dat4          hymt                    realtext
adpcm_ima_dk3           iac                     rka
adpcm_ima_dk4           idcin                   rl2
adpcm_ima_ea_eacs       idf                     roq
adpcm_ima_ea_sead       iff_ilbm                roq_dpcm
adpcm_ima_iss           ilbc                    rpza
adpcm_ima_moflex        imc                     rscc
adpcm_ima_mtf           imm4                    rtv1
adpcm_ima_oki           imm5                    rv10
adpcm_ima_qt            indeo2                  rv20
adpcm_ima_rad           indeo3                  rv30
adpcm_ima_smjpeg        indeo4                  rv40
adpcm_ima_ssi           indeo5                  s302m
adpcm_ima_wav           interplay_acm           sami
adpcm_ima_ws            interplay_dpcm          sanm
adpcm_ms                interplay_video         sbc
adpcm_mtaf              ipu                     scpr
adpcm_psx               jacosub                 screenpresso
adpcm_sbpro_2           jpeg2000                sdx2_dpcm
adpcm_sbpro_3           jpegls                  sga
adpcm_sbpro_4           jv                      sgi
adpcm_swf               kgv1                    sgirle
adpcm_thp               kmvc                    sheervideo
adpcm_thp_le            lagarith                shorten
adpcm_vima              lead                    simbiosis_imx
adpcm_xa                libaom_av1              sipr
adpcm_xmd               libgsm                  siren
adpcm_yamaha            libgsm_ms               smackaud
adpcm_zork              libopencore_amrnb       smacker
agm                     libopencore_amrwb       smc
aic                     libopus                 smvjpeg
alac                    libspeex                snow
alias_pix               libvorbis               sol_dpcm
als                     libvpx_vp8              sonic
amrnb                   libvpx_vp9              sp5x
amrwb                   loco                    speedhq
amv                     lscr                    speex
anm                     m101                    srgc
ansi                    mace3                   srt
anull                   mace6                   ssa
apac                    magicyuv                stl
ape                     mdec                    subrip
apng                    media100                subviewer
aptx                    metasound               subviewer1
aptx_hd                 microdvd                sunrast
arbc                    mimic                   svq1
argo                    misc4                   svq3
ass                     mjpeg                   tak
asv1                    mjpeg_cuvid             targa
asv2                    mjpeg_qsv               targa_y216
atrac1                  mjpegb                  tdsc
atrac3                  mlp                     text
atrac3al                mmvideo                 theora
atrac3p                 mobiclip                thp
atrac3pal               motionpixels            tiertexseqvideo
atrac9                  movtext                 tiff
aura                    mp1                     tmv
aura2                   mp1float                truehd
av1                     mp2                     truemotion1
av1_cuvid               mp2float                truemotion2
av1_qsv                 mp3                     truemotion2rt
avrn                    mp3adu                  truespeech
avrp                    mp3adufloat             tscc
avs                     mp3float                tscc2
avui                    mp3on4                  tta
bethsoftvid             mp3on4float             twinvq
bfi                     mpc7                    txd
bink                    mpc8                    ulti
binkaudio_dct           mpeg1_cuvid             utvideo
binkaudio_rdft          mpeg1video              v210
bintext                 mpeg2_cuvid             v210x
bitpacked               mpeg2_qsv               v308
bmp                     mpeg2video              v408
bmv_audio               mpeg4                   v410
bmv_video               mpeg4_cuvid             vb
bonk                    mpegvideo               vble
brender_pix             mpl2                    vbn
c93                     msa1                    vc1
cavs                    mscc                    vc1_cuvid
cbd2_dpcm               msmpeg4v1               vc1_qsv
ccaption                msmpeg4v2               vc1image
cdgraphics              msmpeg4v3               vcr1
cdtoons                 msnsiren                vmdaudio
cdxl                    msp2                    vmdvideo
cfhd                    msrle                   vmix
cinepak                 mss1                    vmnc
clearvideo              mss2                    vnull
cljr                    msvideo1                vorbis
cllc                    mszh                    vp3
comfortnoise            mts2                    vp4
cook                    mv30                    vp5
cpia                    mvc1                    vp6
cri                     mvc2                    vp6a
cscd                    mvdv                    vp6f
cyuv                    mvha                    vp7
dca                     mwsc                    vp8
dds                     mxpeg                   vp8_cuvid
derf_dpcm               nellymoser              vp8_qsv
dfa                     notchlc                 vp9
dfpwm                   nuv                     vp9_cuvid
dirac                   on2avc                  vp9_qsv
dnxhd                   opus                    vplayer
dolby_e                 osq                     vqa
dpx                     paf_audio               vqc
dsd_lsbf                paf_video               vvc
dsd_lsbf_planar         pam                     vvc_qsv
dsd_msbf                pbm                     wady_dpcm
dsd_msbf_planar         pcm_alaw                wavarc
dsicinaudio             pcm_bluray              wavpack
dsicinvideo             pcm_dvd                 wbmp
dss_sp                  pcm_f16le               wcmv
dst                     pcm_f24le               webp
dvaudio                 pcm_f32be               webvtt
dvbsub                  pcm_f32le               wmalossless
dvdsub                  pcm_f64be               wmapro
dvvideo                 pcm_f64le               wmav1
dxa                     pcm_lxf                 wmav2
dxtory                  pcm_mulaw               wmavoice
dxv                     pcm_s16be               wmv1
eac3                    pcm_s16be_planar        wmv2
eacmv                   pcm_s16le               wmv3
eamad                   pcm_s16le_planar        wmv3image
eatgq                   pcm_s24be               wnv1
eatgv                   pcm_s24daud             wrapped_avframe
eatqi                   pcm_s24le               ws_snd1
eightbps                pcm_s24le_planar        xan_dpcm
eightsvx_exp            pcm_s32be               xan_wc3
eightsvx_fib            pcm_s32le               xan_wc4
escape124               pcm_s32le_planar        xbin
escape130               pcm_s64be               xbm
evrc                    pcm_s64le               xface
exr                     pcm_s8                  xl
fastaudio               pcm_s8_planar           xma1
ffv1                    pcm_sga                 xma2
ffvhuff                 pcm_u16be               xpm
ffwavesynth             pcm_u16le               xsub
fic                     pcm_u24be               xwd
fits                    pcm_u24le               y41p
flac                    pcm_u32be               ylc
flashsv                 pcm_u32le               yop
flashsv2                pcm_u8                  yuv4
flic                    pcm_vidc                zero12v
flv                     pcx                     zerocodec
fmvc                    pdv                     zlib
fourxm                  pfm                     zmbv

Enabled encoders:
a64multi                hevc_mf                 pcm_u24be
a64multi5               hevc_nvenc              pcm_u24le
aac                     hevc_qsv                pcm_u32be
aac_mf                  hevc_vaapi              pcm_u32le
ac3                     huffyuv                 pcm_u8
ac3_fixed               jpeg2000                pcm_vidc
ac3_mf                  jpegls                  pcx
adpcm_adx               libaom_av1              pfm
adpcm_argo              libgsm                  pgm
adpcm_g722              libgsm_ms               pgmyuv
adpcm_g726              libmp3lame              phm
adpcm_g726le            libopencore_amrnb       png
adpcm_ima_alp           libopenjpeg             ppm
adpcm_ima_amv           libopus                 prores
adpcm_ima_apm           libspeex                prores_aw
adpcm_ima_qt            libtheora               prores_ks
adpcm_ima_ssi           libvo_amrwbenc          qoi
adpcm_ima_wav           libvorbis               qtrle
adpcm_ima_ws            libvpx_vp8              r10k
adpcm_ms                libvpx_vp9              r210
adpcm_swf               libwebp                 ra_144
adpcm_yamaha            libwebp_anim            rawvideo
alac                    libx264                 roq
alias_pix               libx264rgb              roq_dpcm
amv                     libx265                 rpza
anull                   libxvid                 rv10
apng                    ljpeg                   rv20
aptx                    magicyuv                s302m
aptx_hd                 mjpeg                   sbc
ass                     mjpeg_qsv               sgi
asv1                    mjpeg_vaapi             smc
asv2                    mlp                     snow
av1_amf                 movtext                 sonic
av1_nvenc               mp2                     sonic_ls
av1_qsv                 mp2fixed                speedhq
av1_vaapi               mp3_mf                  srt
avrp                    mpeg1video              ssa
avui                    mpeg2_qsv               subrip
bitpacked               mpeg2_vaapi             sunrast
bmp                     mpeg2video              svq1
cfhd                    mpeg4                   targa
cinepak                 msmpeg4v2               text
cljr                    msmpeg4v3               tiff
comfortnoise            msrle                   truehd
dca                     msvideo1                tta
dfpwm                   nellymoser              ttml
dnxhd                   opus                    utvideo
dpx                     pam                     v210
dvbsub                  pbm                     v308
dvdsub                  pcm_alaw                v408
dvvideo                 pcm_bluray              v410
dxv                     pcm_dvd                 vbn
eac3                    pcm_f32be               vc2
exr                     pcm_f32le               vnull
ffv1                    pcm_f64be               vorbis
ffvhuff                 pcm_f64le               vp8_vaapi
fits                    pcm_mulaw               vp9_qsv
flac                    pcm_s16be               vp9_vaapi
flashsv                 pcm_s16be_planar        wavpack
flashsv2                pcm_s16le               wbmp
flv                     pcm_s16le_planar        webvtt
g723_1                  pcm_s24be               wmav1
gif                     pcm_s24daud             wmav2
h261                    pcm_s24le               wmv1
h263                    pcm_s24le_planar        wmv2
h263p                   pcm_s32be               wrapped_avframe
h264_amf                pcm_s32le               xbm
h264_mf                 pcm_s32le_planar        xface
h264_nvenc              pcm_s64be               xsub
h264_qsv                pcm_s64le               xwd
h264_vaapi              pcm_s8                  y41p
hdr                     pcm_s8_planar           yuv4
hevc_amf                pcm_u16be               zlib
hevc_d3d12va            pcm_u16le               zmbv

Enabled hwaccels:
av1_d3d11va             hevc_nvdec              vc1_nvdec
av1_d3d11va2            hevc_vaapi              vc1_vaapi
av1_d3d12va             mjpeg_nvdec             vp8_nvdec
av1_dxva2               mjpeg_vaapi             vp8_vaapi
av1_nvdec               mpeg1_nvdec             vp9_d3d11va
av1_vaapi               mpeg2_d3d11va           vp9_d3d11va2
h263_vaapi              mpeg2_d3d11va2          vp9_d3d12va
h264_d3d11va            mpeg2_d3d12va           vp9_dxva2
h264_d3d11va2           mpeg2_dxva2             vp9_nvdec
h264_d3d12va            mpeg2_nvdec             vp9_vaapi
h264_dxva2              mpeg2_vaapi             wmv3_d3d11va
h264_nvdec              mpeg4_nvdec             wmv3_d3d11va2
h264_vaapi              mpeg4_vaapi             wmv3_d3d12va
hevc_d3d11va            vc1_d3d11va             wmv3_dxva2
hevc_d3d11va2           vc1_d3d11va2            wmv3_nvdec
hevc_d3d12va            vc1_d3d12va             wmv3_vaapi
hevc_dxva2              vc1_dxva2

Enabled parsers:
aac                     dvdsub                  mpegaudio
aac_latm                evc                     mpegvideo
ac3                     flac                    opus
adx                     ftr                     png
amr                     g723_1                  pnm
av1                     g729                    qoi
avs2                    gif                     rv34
avs3                    gsm                     sbc
bmp                     h261                    sipr
cavsvideo               h263                    tak
cook                    h264                    vc1
cri                     hdr                     vorbis
dca                     hevc                    vp3
dirac                   ipu                     vp8
dnxhd                   jpeg2000                vp9
dolby_e                 jpegxl                  vvc
dpx                     misc4                   webp
dvaudio                 mjpeg                   xbm
dvbsub                  mlp                     xma
dvd_nav                 mpeg4video              xwd

Enabled demuxers:
aa                      idf                     pcm_mulaw
aac                     iff                     pcm_s16be
aax                     ifv                     pcm_s16le
ac3                     ilbc                    pcm_s24be
ac4                     image2                  pcm_s24le
ace                     image2_alias_pix        pcm_s32be
acm                     image2_brender_pix      pcm_s32le
act                     image2pipe              pcm_s8
adf                     image_bmp_pipe          pcm_u16be
adp                     image_cri_pipe          pcm_u16le
ads                     image_dds_pipe          pcm_u24be
adx                     image_dpx_pipe          pcm_u24le
aea                     image_exr_pipe          pcm_u32be
afc                     image_gem_pipe          pcm_u32le
aiff                    image_gif_pipe          pcm_u8
aix                     image_hdr_pipe          pcm_vidc
alp                     image_j2k_pipe          pdv
amr                     image_jpeg_pipe         pjs
amrnb                   image_jpegls_pipe       pmp
amrwb                   image_jpegxl_pipe       pp_bnk
anm                     image_pam_pipe          pva
apac                    image_pbm_pipe          pvf
apc                     image_pcx_pipe          qcp
ape                     image_pfm_pipe          qoa
apm                     image_pgm_pipe          r3d
apng                    image_pgmyuv_pipe       rawvideo
aptx                    image_pgx_pipe          rcwt
aptx_hd                 image_phm_pipe          realtext
aqtitle                 image_photocd_pipe      redspark
argo_asf                image_pictor_pipe       rka
argo_brp                image_png_pipe          rl2
argo_cvg                image_ppm_pipe          rm
asf                     image_psd_pipe          roq
asf_o                   image_qdraw_pipe        rpl
ass                     image_qoi_pipe          rsd
ast                     image_sgi_pipe          rso
au                      image_sunrast_pipe      rtp
av1                     image_svg_pipe          rtsp
avi                     image_tiff_pipe         s337m
avisynth                image_vbn_pipe          sami
avr                     image_webp_pipe         sap
avs                     image_xbm_pipe          sbc
avs2                    image_xpm_pipe          sbg
avs3                    image_xwd_pipe          scc
bethsoftvid             imf                     scd
bfi                     ingenient               sdns
bfstm                   ipmovie                 sdp
bink                    ipu                     sdr2
binka                   ircam                   sds
bintext                 iss                     sdx
bit                     iv8                     segafilm
bitpacked               ivf                     ser
bmv                     ivr                     sga
boa                     jacosub                 shorten
bonk                    jpegxl_anim             siff
brstm                   jv                      simbiosis_imx
c93                     kux                     sln
caf                     kvag                    smacker
cavsvideo               laf                     smjpeg
cdg                     lc3                     smush
cdxl                    libgme                  sol
cine                    libopenmpt              sox
codec2                  live_flv                spdif
codec2raw               lmlm4                   srt
concat                  loas                    stl
dash                    lrc                     str
data                    luodat                  subviewer
daud                    lvf                     subviewer1
dcstr                   lxf                     sup
derf                    m4v                     svag
dfa                     matroska                svs
dfpwm                   mca                     swf
dhav                    mcc                     tak
dirac                   mgsts                   tedcaptions
dnxhd                   microdvd                thp
dsf                     mjpeg                   threedostr
dsicin                  mjpeg_2000              tiertexseq
dss                     mlp                     tmv
dts                     mlv                     truehd
dtshd                   mm                      tta
dv                      mmf                     tty
dvbsub                  mods                    txd
dvbtxt                  moflex                  ty
dxa                     mov                     usm
ea                      mp3                     v210
ea_cdata                mpc                     v210x
eac3                    mpc8                    vag
epaf                    mpegps                  vc1
evc                     mpegts                  vc1t
ffmetadata              mpegtsraw               vividas
filmstrip               mpegvideo               vivo
fits                    mpjpeg                  vmd
flac                    mpl2                    vobsub
flic                    mpsub                   voc
flv                     msf                     vpk
fourxm                  msnwc_tcp               vplayer
frm                     msp                     vqf
fsb                     mtaf                    vvc
fwse                    mtv                     w64
g722                    musx                    wady
g723_1                  mv                      wav
g726                    mvi                     wavarc
g726le                  mxf                     wc3
g729                    mxg                     webm_dash_manifest
gdv                     nc                      webvtt
genh                    nistsphere              wsaud
gif                     nsp                     wsd
gsm                     nsv                     wsvqa
gxf                     nut                     wtv
h261                    nuv                     wv
h263                    obu                     wve
h264                    ogg                     xa
hca                     oma                     xbin
hcom                    osq                     xmd
hevc                    paf                     xmv
hls                     pcm_alaw                xvag
hnm                     pcm_f32be               xwma
iamf                    pcm_f32le               yop
ico                     pcm_f64be               yuv4mpegpipe
idcin                   pcm_f64le

Enabled muxers:
a64                     h263                    pcm_s16le
ac3                     h264                    pcm_s24be
ac4                     hash                    pcm_s24le
adts                    hds                     pcm_s32be
adx                     hevc                    pcm_s32le
aea                     hls                     pcm_s8
aiff                    iamf                    pcm_u16be
alp                     ico                     pcm_u16le
amr                     ilbc                    pcm_u24be
amv                     image2                  pcm_u24le
apm                     image2pipe              pcm_u32be
apng                    ipod                    pcm_u32le
aptx                    ircam                   pcm_u8
aptx_hd                 ismv                    pcm_vidc
argo_asf                ivf                     psp
argo_cvg                jacosub                 rawvideo
asf                     kvag                    rcwt
asf_stream              latm                    rm
ass                     lc3                     roq
ast                     lrc                     rso
au                      m4v                     rtp
avi                     matroska                rtp_mpegts
avif                    matroska_audio          rtsp
avm2                    md5                     sap
avs2                    microdvd                sbc
avs3                    mjpeg                   scc
bit                     mkvtimestamp_v2         segafilm
caf                     mlp                     segment
cavsvideo               mmf                     smjpeg
codec2                  mov                     smoothstreaming
codec2raw               mp2                     sox
crc                     mp3                     spdif
dash                    mp4                     spx
data                    mpeg1system             srt
daud                    mpeg1vcd                stream_segment
dfpwm                   mpeg1video              streamhash
dirac                   mpeg2dvd                sup
dnxhd                   mpeg2svcd               swf
dts                     mpeg2video              tee
dv                      mpeg2vob                tg2
eac3                    mpegts                  tgp
evc                     mpjpeg                  truehd
f4v                     mxf                     tta
ffmetadata              mxf_d10                 ttml
fifo                    mxf_opatom              uncodedframecrc
filmstrip               null                    vc1
fits                    nut                     vc1t
flac                    obu                     voc
flv                     oga                     vvc
framecrc                ogg                     w64
framehash               ogv                     wav
framemd5                oma                     webm
g722                    opus                    webm_chunk
g723_1                  pcm_alaw                webm_dash_manifest
g726                    pcm_f32be               webp
g726le                  pcm_f32le               webvtt
gif                     pcm_f64be               wsaud
gsm                     pcm_f64le               wtv
gxf                     pcm_mulaw               wv
h261                    pcm_s16be               yuv4mpegpipe

Enabled protocols:
async                   http                    rtmp
cache                   httpproxy               rtmpe
concat                  https                   rtmps
concatf                 icecast                 rtmpt
crypto                  ipfs_gateway            rtmpte
data                    ipns_gateway            rtmpts
fd                      libsrt                  rtp
ffrtmpcrypt             libssh                  srtp
ffrtmphttp              libzmq                  subfile
file                    md5                     tcp
ftp                     mmsh                    tee
gopher                  mmst                    tls
gophers                 pipe                    udp
hls                     prompeg                 udplite

Enabled filters:
a3dscope                curves                  palettegen
aap                     datascope               paletteuse
abench                  dblur                   pan
abitscope               dcshift                 perlin
acompressor             dctdnoiz                perms
acontrast               ddagrab                 perspective
acopy                   deband                  phase
acrossfade              deblock                 photosensitivity
acrossover              decimate                pixdesctest
acrusher                deconvolve              pixelize
acue                    dedot                   pixscope
addroi                  deesser                 pp
adeclick                deflate                 pp7
adeclip                 deflicker               premultiply
adecorrelate            deinterlace_qsv         prewitt
adelay                  deinterlace_vaapi       procamp_vaapi
adenorm                 dejudder                pseudocolor
aderivative             delogo                  psnr
adrawgraph              denoise_vaapi           pullup
adrc                    deshake                 qp
adynamicequalizer       despill                 random
adynamicsmooth          detelecine              readeia608
aecho                   dialoguenhance          readvitc
aemphasis               dilation                realtime
aeval                   displace                remap
aevalsrc                doubleweave             removegrain
aexciter                drawbox                 removelogo
afade                   drawbox_vaapi           repeatfields
afdelaysrc              drawgraph               replaygain
afftdn                  drawgrid                reverse
afftfilt                drawtext                rgbashift
afir                    drmeter                 rgbtestsrc
afireqsrc               dynaudnorm              roberts
afirsrc                 earwax                  rotate
aformat                 ebur128                 rubberband
afreqshift              edgedetect              sab
afwtdn                  elbg                    scale
agate                   entropy                 scale2ref
agraphmonitor           epx                     scale_cuda
ahistogram              eq                      scale_qsv
aiir                    equalizer               scale_vaapi
aintegral               erosion                 scdet
ainterleave             estdif                  scharr
alatency                exposure                scroll
alimiter                extractplanes           segment
allpass                 extrastereo             select
allrgb                  fade                    selectivecolor
allyuv                  feedback                sendcmd
aloop                   fftdnoiz                separatefields
alphaextract            fftfilt                 setdar
alphamerge              field                   setfield
amerge                  fieldhint               setparams
ametadata               fieldmatch              setpts
amix                    fieldorder              setrange
amovie                  fillborders             setsar
amplify                 find_rect               settb
amultiply               firequalizer            sharpness_vaapi
anequalizer             flanger                 shear
anlmdn                  floodfill               showcqt
anlmf                   format                  showcwt
anlms                   fps                     showfreqs
anoisesrc               framepack               showinfo
anull                   framerate               showpalette
anullsink               framestep               showspatial
anullsrc                freezedetect            showspectrum
apad                    freezeframes            showspectrumpic
aperms                  fspp                    showvolume
aphasemeter             fsync                   showwaves
aphaser                 gblur                   showwavespic
aphaseshift             geq                     shuffleframes
apsnr                   gradfun                 shufflepixels
apsyclip                gradients               shuffleplanes
apulsator               graphmonitor            sidechaincompress
arealtime               grayworld               sidechaingate
aresample               greyedge                sidedata
areverse                guided                  sierpinski
arls                    haas                    signalstats
arnndn                  haldclut                signature
asdr                    haldclutsrc             silencedetect
asegment                hdcd                    silenceremove
aselect                 headphone               sinc
asendcmd                hflip                   sine
asetnsamples            highpass                siti
asetpts                 highshelf               smartblur
asetrate                hilbert                 smptebars
asettb                  histeq                  smptehdbars
ashowinfo               histogram               sobel
asidedata               hqdn3d                  spectrumsynth
asisdr                  hqx                     speechnorm
asoftclip               hstack                  split
aspectralstats          hstack_qsv              spp
asplit                  hstack_vaapi            ssim
ass                     hsvhold                 ssim360
astats                  hsvkey                  stereo3d
astreamselect           hue                     stereotools
asubboost               huesaturation           stereowiden
asubcut                 hwdownload              streamselect
asupercut               hwmap                   subtitles
asuperpass              hwupload                super2xsai
asuperstop              hwupload_cuda           superequalizer
atadenoise              hysteresis              surround
atempo                  identity                swaprect
atilt                   idet                    swapuv
atrim                   il                      tblend
avectorscope            inflate                 telecine
avgblur                 interlace               testsrc
avsynctest              interleave              testsrc2
axcorrelate             join                    thistogram
azmq                    kerndeint               threshold
backgroundkey           kirsch                  thumbnail
bandpass                lagfun                  thumbnail_cuda
bandreject              latency                 tile
bass                    lenscorrection          tiltandshift
bbox                    libvmaf                 tiltshelf
bench                   life                    tinterlace
bilateral               limitdiff               tlut2
bilateral_cuda          limiter                 tmedian
biquad                  loop                    tmidequalizer
bitplanenoise           loudnorm                tmix
blackdetect             lowpass                 tonemap
blackframe              lowshelf                tonemap_vaapi
blend                   lumakey                 tpad
blockdetect             lut                     transpose
blurdetect              lut1d                   transpose_vaapi
bm3d                    lut2                    treble
boxblur                 lut3d                   tremolo
bwdif                   lutrgb                  trim
bwdif_cuda              lutyuv                  unpremultiply
cas                     mandelbrot              unsharp
ccrepack                maskedclamp             untile
cellauto                maskedmax               uspp
channelmap              maskedmerge             v360
channelsplit            maskedmin               vaguedenoiser
chorus                  maskedthreshold         varblur
chromahold              maskfun                 vectorscope
chromakey               mcdeint                 vflip
chromakey_cuda          mcompand                vfrdet
chromanr                median                  vibrance
chromashift             mergeplanes             vibrato
ciescope                mestimate               vidstabdetect
codecview               metadata                vidstabtransform
color                   midequalizer            vif
colorbalance            minterpolate            vignette
colorchannelmixer       mix                     virtualbass
colorchart              monochrome              vmafmotion
colorcontrast           morpho                  volume
colorcorrect            movie                   volumedetect
colorhold               mpdecimate              vpp_qsv
colorize                mptestsrc               vstack
colorkey                msad                    vstack_qsv
colorlevels             multiply                vstack_vaapi
colormap                negate                  w3fdif
colormatrix             nlmeans                 waveform
colorspace              nnedi                   weave
colorspace_cuda         noformat                xbr
colorspectrum           noise                   xcorrelate
colortemperature        normalize               xfade
compand                 null                    xmedian
compensationdelay       nullsink                xpsnr
concat                  nullsrc                 xstack
convolution             oscilloscope            xstack_qsv
convolve                overlay                 xstack_vaapi
copy                    overlay_cuda            yadif
corr                    overlay_qsv             yadif_cuda
cover_rect              overlay_vaapi           yaepblur
crop                    owdenoise               yuvtestsrc
cropdetect              pad                     zmq
crossfeed               pad_vaapi               zoneplate
crystalizer             pal100bars              zoompan
cue                     pal75bars               zscale

Enabled bsfs:
aac_adtstoasc           h264_mp4toannexb        pcm_rechunk
av1_frame_merge         h264_redundant_pps      pgs_frame_merge
av1_frame_split         hapqa_extract           prores_metadata
av1_metadata            hevc_metadata           remove_extradata
chomp                   hevc_mp4toannexb        setts
dca_core                imx_dump_header         showinfo
dovi_rpu                media100_to_mjpegb      text2movsub
dts2pts                 mjpeg2jpeg              trace_headers
dump_extradata          mjpega_dump_header      truehd_core
dv_error_marker         mov2textsub             vp9_metadata
eac3_core               mpeg2_metadata          vp9_raw_reorder
evc_frame_merge         mpeg4_unpack_bframes    vp9_superframe
extract_extradata       noise                   vp9_superframe_split
filter_units            null                    vvc_metadata
h264_metadata           opus_metadata           vvc_mp4toannexb

Enabled indevs:
dshow                   lavfi
gdigrab                 vfwcap

Enabled outdevs:
sdl2

release-essentials external libraries' versions: 

AMF v1.4.36.0
aom v3.12.0-20-g20f697ad51
AviSynthPlus v3.7.3-211-gb038d022
ffnvcodec n13.0.19.0-1-gf2fb9b3
freetype VER-2-13-3
fribidi v1.0.16-2-gb28f43b
gsm 1.0.22
harfbuzz 10.4.0-151-g79c991e1
lame 3.100
libass 0.17.3-79-g1b69955
libgme 0.6.3
libopencore-amrnb 0.1.6
libopencore-amrwb 0.1.6
libssh 0.11.1
libtheora 1.1.1
libwebp v1.5.0-12-g1d86819f
oneVPL 2.14
openmpt libopenmpt-0.6.22-19-g9ae5dfb5b
opus v1.5.2-73-gc79a9bd1
rubberband v1.8.1
SDL release-2.32.0-15-g22a87a22c
speex Speex-1.2.1-45-g4e231b4
srt v1.5.4-25-g697dce0
VAAPI 2.23.0.
vidstab v1.1.1-14-gd2d55a8
vmaf v3.0.0-107-g4db7c0c8
vo-amrwbenc 0.1.3
vorbis v1.3.7-10-g84c02369
vpx v1.15.0-65-g95afae324
x264 v0.164.3204
x265 4.1-110-g0e0eee580
xvid v1.3.7
zeromq 4.3.5
zimg release-3.0.5-197-g9a9a8ea

