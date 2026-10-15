// Casos de prueba de nestjs-seguridad.yaml (se ejecutan con semgrep --test).
// Contiene código inseguro A PROPÓSITO. No es código del servicio ni se despliega.

// ---------- nestjs-validationpipe-sin-whitelist ----------
// ruleid: nestjs-validationpipe-sin-whitelist
app.useGlobalPipes(new ValidationPipe());
// ruleid: nestjs-validationpipe-sin-whitelist
app.useGlobalPipes(new ValidationPipe({ transform: true }));
// ok: nestjs-validationpipe-sin-whitelist
app.useGlobalPipes(new ValidationPipe({ whitelist: true, forbidNonWhitelisted: true }));

// ---------- prisma-sql-crudo-inseguro ----------
// ruleid: prisma-sql-crudo-inseguro
prisma.$queryRawUnsafe(`SELECT * FROM usuarios WHERE correo = '${correo}'`);
// ruleid: prisma-sql-crudo-inseguro
this.prisma.$executeRawUnsafe('DELETE FROM usuarios WHERE id = ' + id);
// ok: prisma-sql-crudo-inseguro
prisma.$queryRaw`SELECT * FROM usuarios WHERE correo = ${correo}`;

// ---------- nestjs-cors-abierto ----------
// ruleid: nestjs-cors-abierto
app.enableCors();
// ruleid: nestjs-cors-abierto
app.enableCors({ origin: '*' });
// ruleid: nestjs-cors-abierto
app.enableCors({ origin: true, credentials: true });
// ruleid: nestjs-cors-abierto
const appAbierta = NestFactory.create(AppModule, { cors: true });
// ok: nestjs-cors-abierto
app.enableCors({ origin: ['https://tienda.example.com'], credentials: true });

// ---------- jwt-secreto-en-codigo ----------
// ruleid: jwt-secreto-en-codigo
JwtModule.register({ secret: 'cambiame', signOptions: { expiresIn: '1h' } });
class EstrategiaConSecreto {
  constructor() {
    // ruleid: jwt-secreto-en-codigo
    super({ secretOrKey: 'cambiame' });
  }
}
// ruleid: jwt-secreto-en-codigo
const estrategia = new Strategy({ secretOrKey: 'cambiame' });
// ruleid: jwt-secreto-en-codigo
const token = jwt.sign({ sub: '1' }, 'cambiame');
// ruleid: jwt-secreto-en-codigo
this.jwtService.sign(payload, { secret: 'cambiame' });
// ok: jwt-secreto-en-codigo
JwtModule.register({ secret: process.env.JWT_SECRET });
// ok: jwt-secreto-en-codigo
const tokenSeguro = jwt.sign({ sub: '1' }, process.env.JWT_SECRET);

// ---------- jwt-ignora-expiracion ----------
class EstrategiaSinExpiracion {
  constructor() {
    // ruleid: jwt-ignora-expiracion
    super({ ignoreExpiration: true });
  }
}
// ruleid: jwt-ignora-expiracion
jwt.verify(token, clave, { ignoreExpiration: true });
// ok: jwt-ignora-expiracion
jwt.verify(token, clave, { ignoreExpiration: false });

// ---------- tls-verificacion-desactivada ----------
// ruleid: tls-verificacion-desactivada
https.request({ host: 'api.example.com', rejectUnauthorized: false });
// ruleid: tls-verificacion-desactivada
new Agent({ rejectUnauthorized: false });
// ruleid: tls-verificacion-desactivada
new PrismaPg({ connectionString, ssl: { rejectUnauthorized: false } });
// ruleid: tls-verificacion-desactivada
process.env.NODE_TLS_REJECT_UNAUTHORIZED = '0';
// ok: tls-verificacion-desactivada
new PrismaPg({ connectionString, ssl: { rejectUnauthorized: true } });

// ---------- hash-criptografico-debil ----------
// ruleid: hash-criptografico-debil
const huellaMd5 = createHash('md5').update(dato).digest('hex');
// ruleid: hash-criptografico-debil
const huellaSha1 = crypto.createHash('sha1').update(dato).digest('hex');
// ok: hash-criptografico-debil
const huellaSha256 = createHash('sha256').update(dato).digest('hex');

// ---------- prisma-findmany-sin-limite ----------
// ruleid: prisma-findmany-sin-limite
this.prisma.usuario.findMany();
// ruleid: prisma-findmany-sin-limite
this.prisma.usuario.findMany({ where: { activo: true } });
// ok: prisma-findmany-sin-limite
this.prisma.usuario.findMany({ take: 100 });
// ok: prisma-findmany-sin-limite
this.prisma.usuario.findMany({ orderBy: { creadoEn: 'asc' }, take: 100 });
