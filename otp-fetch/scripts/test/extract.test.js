'use strict';
// Unit tests for the pure parts of otp.js. No network, no IMAP.
//   node test/extract.test.js
// Samples are shaped like the real mail from the services this actually gets
// pointed at: Booking.com, Google, Amazon, iHerb, ticketjam.

const assert = require('node:assert');
const { extractCode, resolveSince, readEnvFile } = require('../otp.js');

let pass = 0;
let fail = 0;
function t(name, fn) {
  try { fn(); pass++; console.log('PASS  ' + name); }
  catch (e) { fail++; console.log('FAIL  ' + name + '\n      ' + e.message); }
}

// ------------------------------------------------------------ real shapes ---

t('Booking.com verification mail', () => {
  assert.strictEqual(extractCode(
    'Your Booking.com verification code\n\nHi Javier,\n' +
    'Enter this code to sign in: 483920\n' +
    'It expires in 10 minutes. Property ID 1234567.'), '483920');
});

t('Google 2-step ("G-" prefixed)', () => {
  assert.strictEqual(extractCode(
    'G-704193 is your Google verification code'), '704193');
});

t('Amazon OTP', () => {
  assert.strictEqual(extractCode(
    'Amazon\nTo authenticate, please use the following One Time Password (OTP): 291845\n' +
    'Do not share this OTP with anyone. Order 114-2938471-9928374.'), '291845');
});

t('iHerb sign-in code', () => {
  assert.strictEqual(extractCode(
    'iHerb security code\nYour verification code is 55210.\nOrder total $41.36.'), '55210');
});

t('ticketjam Japanese 2FA', () => {
  assert.strictEqual(extractCode(
    '\u3010\u30c1\u30b1\u30c3\u30c8\u30b8\u30e3\u30e0\u3011\u4e8c\u6bb5\u968e\u8a8d\u8fc4\n' +
    '\u8a8d\u8fc4\u30b3\u30fc\u30c9: 918273\n30\u5206\u4ee5\u5185\u306b\u5165\u529b\u3057\u3066\u304f\u3060\u3055\u3044\u3002'), '918273');
});

t('Spanish "codigo de verificacion"', () => {
  assert.strictEqual(extractCode(
    'Tu c\u00f3digo de verificaci\u00f3n es 604815. Caduca en 5 minutos.'), '604815');
});

t('alphanumeric code', () => {
  assert.strictEqual(extractCode(
    'Your security code: A4F9K2'), 'A4F9K2');
});

t('code appearing before the label', () => {
  assert.strictEqual(extractCode(
    '773311 is your verification code for Resy'), '773311');
});

// ----------------------------------------------------- the bare-run fallback ---

t('unlabelled mail with one 6-digit run', () => {
  assert.strictEqual(extractCode(
    'Confirm your sign in\n\n449021\n\nIf this was not you, ignore this mail.'), '449021');
});

t('unlabelled mail with two different 6-digit runs is refused', () => {
  assert.strictEqual(extractCode(
    'Reference 449021 relates to shipment 883910 leaving today.'), null);
});

t('prices and years are not codes', () => {
  assert.strictEqual(extractCode(
    'Your 2026 statement is ready. Balance $124556.00 as of today.'), null);
});

t('an order number glued to letters is not a code', () => {
  assert.strictEqual(extractCode(
    'Tracking ID AB123456CD is now in transit.'), null);
});

t('mail with no code at all', () => {
  assert.strictEqual(extractCode(
    'Your reservation is confirmed. See you on Thursday.'), null);
});

t('custom pattern wins over the heuristics', () => {
  assert.strictEqual(extractCode(
    'PIN 1234 / token ZZ-88-QQ', 'token ([A-Z]{2}-\\d{2}-[A-Z]{2})'), 'ZZ-88-QQ');
});

// ------------------------------------------------------------------ --since ---

t('--since now is at or after the call', () => {
  const before = Date.now();
  const d = resolveSince('now');
  assert.ok(d.getTime() >= before - 5 && d.getTime() <= Date.now() + 5);
});

t('--since -90s looks back ninety seconds', () => {
  const d = resolveSince('-90s');
  const delta = Date.now() - d.getTime();
  assert.ok(delta >= 89000 && delta <= 91500, 'delta was ' + delta);
});

t('--since -5m looks back five minutes', () => {
  const delta = Date.now() - resolveSince('-5m').getTime();
  assert.ok(delta >= 299000 && delta <= 301500, 'delta was ' + delta);
});

t('--since accepts an ISO timestamp', () => {
  assert.strictEqual(resolveSince('2026-09-08T12:00:00Z').toISOString(), '2026-09-08T12:00:00.000Z');
});

// ---------------------------------------------------------------- env file ---

t('readEnvFile on a missing file returns empty, does not throw', () => {
  assert.deepStrictEqual(readEnvFile('C:/nope/definitely-not-here.env'), {});
});

console.log('\n' + pass + ' passed, ' + fail + ' failed');
process.exit(fail ? 1 : 0);
