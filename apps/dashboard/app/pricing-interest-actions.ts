'use server';

import { redirect } from 'next/navigation';

const RECIPIENT_EMAIL =
  process.env.DAAI_PRICING_INTEREST_RECIPIENT_EMAIL?.trim() ||
  'sany.alam.au@gmail.com';
const FROM_EMAIL =
  process.env.DAAI_PRICING_INTEREST_EMAIL_FROM?.trim() ||
  process.env.DAAI_APPROVAL_EMAIL_FROM?.trim() ||
  'DAAI Console <hello@daaihq.com>';
const MAX_EMAIL_LENGTH = 254;
const MAX_NOTE_LENGTH = 700;

function readString(formData: FormData, key: string): string {
  const value = formData.get(key);
  return typeof value === 'string' ? value.trim() : '';
}

function isValidEmail(email: string): boolean {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function redirectToPricing(status: 'sent' | 'invalid' | 'failed'): never {
  redirect(`/?pricing_interest=${status}#paid-interest`);
}

function buildEmailBody(email: string, note: string): string {
  return [
    'New higher capacity access interest submission.',
    '',
    `Email: ${email}`,
    `Short note: ${note || 'No note provided.'}`,
    `Submitted at: ${new Date().toISOString()}`,
  ].join('\n');
}

async function sendPricingInterestEmail(email: string, note: string): Promise<boolean> {
  const resendApiKey = process.env.DAAI_RESEND_API_KEY?.trim();
  if (!resendApiKey) {
    console.error('DAAI_RESEND_API_KEY is missing; pricing interest email was not sent.');
    return false;
  }

  try {
    const response = await fetch('https://api.resend.com/emails', {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${resendApiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        from: FROM_EMAIL,
        to: [RECIPIENT_EMAIL],
        reply_to: email,
        subject: 'DAAI higher capacity access interest',
        text: buildEmailBody(email, note),
      }),
    });

    if (!response.ok) {
      console.error(
        'Resend pricing interest email failed:',
        response.status,
        await response.text(),
      );
      return false;
    }
  } catch (error) {
    console.error('Pricing interest email request failed:', error);
    return false;
  }

  return true;
}

export async function submitPricingInterest(formData: FormData): Promise<never> {
  const honeypot = readString(formData, 'company_website');
  if (honeypot) {
    redirectToPricing('sent');
  }

  const email = readString(formData, 'email').slice(0, MAX_EMAIL_LENGTH);
  const note = readString(formData, 'note').slice(0, MAX_NOTE_LENGTH);
  if (!email || !isValidEmail(email)) {
    redirectToPricing('invalid');
  }

  const sent = await sendPricingInterestEmail(email, note);
  redirectToPricing(sent ? 'sent' : 'failed');
}
