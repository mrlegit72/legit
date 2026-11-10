import { PrismaClient } from '@prisma/client'
import bcrypt from 'bcryptjs'

const prisma = new PrismaClient()

async function main() {
  console.log('🌱 Seeding AjoVault database...')

  // Clean existing data
  await prisma.notification.deleteMany()
  await prisma.transaction.deleteMany()
  await prisma.charge.deleteMany()
  await prisma.contribution.deleteMany()
  await prisma.groupMember.deleteMany()
  await prisma.group.deleteMany()
  await prisma.wallet.deleteMany()
  await prisma.auditLog.deleteMany()
  await prisma.amlFlag.deleteMany()
  await prisma.withdrawalRequest.deleteMany()
  await prisma.user.deleteMany()
  await prisma.providerConfig.deleteMany()
  await prisma.countryConfig.deleteMany()
  await prisma.setting.deleteMany()

  const password = await bcrypt.hash('password123', 10)

  // Users — adaeze is the seeded platform admin.
  const adaeze = await prisma.user.create({
    data: {
      name: 'Adaeze Okafor',
      email: 'adaeze@demo.com',
      phone: '+2348012345678',
      country: 'Nigeria',
      password,
      image: 'https://api.dicebear.com/7.x/avataaars/svg?seed=Adaeze',
      role: 'admin',
      kycStatus: 'verified',
      wallet: { create: { balance: 450 } },
    },
  })

  const kwame = await prisma.user.create({
    data: {
      name: 'Kwame Mensah',
      email: 'kwame@demo.com',
      phone: '+233501234567',
      country: 'Ghana',
      password,
      image: 'https://api.dicebear.com/7.x/avataaars/svg?seed=Kwame',
      wallet: { create: { balance: 1200 } },
    },
  })

  const chinedu = await prisma.user.create({
    data: {
      name: 'Chinedu Balogun',
      email: 'chinedu@demo.com',
      phone: '+2348098765432',
      country: 'Nigeria',
      password,
      image: 'https://api.dicebear.com/7.x/avataaars/svg?seed=Chinedu',
      wallet: { create: { balance: 80 } },
    },
  })

  const fatima = await prisma.user.create({
    data: {
      name: 'Fatima Abubakar',
      email: 'fatima@demo.com',
      phone: '+2347011122233',
      country: 'Nigeria',
      password,
      image: 'https://api.dicebear.com/7.x/avataaars/svg?seed=Fatima',
      wallet: { create: { balance: 220 } },
    },
  })

  const akosua = await prisma.user.create({
    data: {
      name: 'Akosua Owusu',
      email: 'akosua@demo.com',
      phone: '+233244556677',
      country: 'Ghana',
      password,
      image: 'https://api.dicebear.com/7.x/avataaars/svg?seed=Akosua',
      wallet: { create: { balance: 640 } },
    },
  })

  const users = [adaeze, kwame, chinedu, fatima, akosua]

  // Groups
  const activeGroup1 = await prisma.group.create({
    data: {
      name: 'Lagos Traders Circle',
      description: 'Weekly savings group for market vendors in Balogun.',
      contributionAmount: 100,
      frequency: 'weekly',
      maxMembers: 10,
      startDate: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
      status: 'active',
      currentCycle: 4,
      payoutOrder: 'rotation',
      members: {
        create: users.map((u, i) => ({
          userId: u.id,
          position: i + 1,
          hasReceivedPot: i < 3,
        })),
      },
    },
  })

  const activeGroup2 = await prisma.group.create({
    data: {
      name: 'Accra Builders Ajo',
      description: 'Monthly savings for real estate deposits.',
      contributionAmount: 500,
      frequency: 'monthly',
      maxMembers: 8,
      startDate: new Date(Date.now() - 60 * 24 * 60 * 60 * 1000),
      status: 'active',
      currentCycle: 2,
      payoutOrder: 'rotation',
      members: {
        create: [adaeze, kwame, akosua].map((u, i) => ({
          userId: u.id,
          position: i + 1,
          hasReceivedPot: i < 1,
        })),
      },
    },
  })

  const completedGroup = await prisma.group.create({
    data: {
      name: 'Abuja Tech Founders Pool',
      description: 'Completed — funded 6 startup licenses.',
      contributionAmount: 250,
      frequency: 'monthly',
      maxMembers: 6,
      startDate: new Date(Date.now() - 200 * 24 * 60 * 60 * 1000),
      status: 'completed',
      currentCycle: 6,
      payoutOrder: 'rotation',
      members: {
        create: [adaeze, chinedu, fatima].map((u, i) => ({
          userId: u.id,
          position: i + 1,
          hasReceivedPot: true,
        })),
      },
    },
  })

  const pendingGroup = await prisma.group.create({
    data: {
      name: 'Kumasi Women Co-op',
      description: 'Starting next week. 3 more members needed.',
      contributionAmount: 75,
      frequency: 'weekly',
      maxMembers: 12,
      startDate: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000),
      status: 'pending',
      currentCycle: 0,
      payoutOrder: 'first_come',
      members: {
        create: [kwame, akosua, fatima].map((u, i) => ({
          userId: u.id,
          position: i + 1,
        })),
      },
    },
  })

  const fullGroup = await prisma.group.create({
    data: {
      name: 'Port Harcourt Motorists',
      description: 'Saving for vehicle parts and maintenance.',
      contributionAmount: 150,
      frequency: 'weekly',
      maxMembers: 5,
      startDate: new Date(Date.now() - 14 * 24 * 60 * 60 * 1000),
      status: 'active',
      currentCycle: 2,
      payoutOrder: 'rotation',
      members: {
        create: users.map((u, i) => ({
          userId: u.id,
          position: i + 1,
          hasReceivedPot: i < 2,
        })),
      },
    },
  })

  // Contributions
  for (const g of [activeGroup1, activeGroup2, fullGroup]) {
    for (let c = 1; c <= g.currentCycle; c++) {
      for (const u of users.slice(0, 3)) {
        await prisma.contribution.create({
          data: {
            userId: u.id,
            groupId: g.id,
            amount: g.contributionAmount,
            cycle: c,
            status: 'confirmed',
          },
        })
      }
    }
  }

  // Transactions
  const txTypes = [
    { type: 'deposit', amount: 500, status: 'completed', description: 'Coinbase Commerce USDT deposit' },
    { type: 'contribution', amount: 100, status: 'completed', description: 'Lagos Traders Circle — Cycle 4' },
    { type: 'payout', amount: 1000, status: 'completed', description: 'Lagos Traders Circle — Pot received' },
    { type: 'withdrawal', amount: 300, status: 'pending', description: 'Withdraw to GTBank ****2341' },
    { type: 'deposit', amount: 250, status: 'completed', description: 'Coinbase Commerce USDT deposit' },
    { type: 'contribution', amount: 500, status: 'completed', description: 'Accra Builders Ajo — Cycle 2' },
    { type: 'deposit', amount: 1200, status: 'completed', description: 'Initial top-up' },
    { type: 'contribution', amount: 75, status: 'pending', description: 'Kumasi Women Co-op — Cycle 1' },
    { type: 'withdrawal', amount: 150, status: 'completed', description: 'Withdraw to Zenith ****8812' },
    { type: 'payout', amount: 750, status: 'completed', description: 'Abuja Tech Founders Pool — Final' },
    { type: 'deposit', amount: 80, status: 'completed', description: 'Coinbase Commerce USDC deposit' },
    { type: 'contribution', amount: 150, status: 'completed', description: 'Port Harcourt Motorists — Cycle 2' },
    { type: 'contribution', amount: 150, status: 'completed', description: 'Port Harcourt Motorists — Cycle 1' },
    { type: 'deposit', amount: 400, status: 'completed', description: 'Coinbase Commerce BTC deposit' },
    { type: 'withdrawal', amount: 200, status: 'failed', description: 'Withdraw to Access ****0099' },
    { type: 'contribution', amount: 250, status: 'completed', description: 'Abuja Tech Founders Pool — Cycle 6' },
    { type: 'payout', amount: 500, status: 'completed', description: 'Port Harcourt Motorists — Pot received' },
    { type: 'deposit', amount: 600, status: 'completed', description: 'Coinbase Commerce ETH deposit' },
    { type: 'contribution', amount: 100, status: 'completed', description: 'Lagos Traders Circle — Cycle 3' },
    { type: 'contribution', amount: 100, status: 'completed', description: 'Lagos Traders Circle — Cycle 2' },
    { type: 'contribution', amount: 100, status: 'completed', description: 'Lagos Traders Circle — Cycle 1' },
  ]

  let offset = 0
  for (const u of users) {
    const slice = txTypes.slice(offset, offset + 5)
    for (let i = 0; i < slice.length; i++) {
      const t = slice[i]
      await prisma.transaction.create({
        data: {
          userId: u.id,
          type: t.type,
          amount: t.amount,
          status: t.status,
          description: t.description,
          createdAt: new Date(Date.now() - (i + 1) * 2 * 24 * 60 * 60 * 1000),
        },
      })
    }
    offset = (offset + 4) % txTypes.length
  }

  // Notifications
  for (const u of users) {
    await prisma.notification.createMany({
      data: [
        { userId: u.id, title: 'Welcome to AjoVault', message: 'Your wallet is ready. Start saving today.' },
        { userId: u.id, title: 'Contribution confirmed', message: 'Your cycle contribution has been received.' },
        { userId: u.id, title: 'Payout scheduled', message: 'Your payout is scheduled in 3 days.', read: true },
      ],
    })
  }

  // Pending withdrawal requests for the admin queue
  await prisma.withdrawalRequest.create({
    data: {
      userId: kwame.id,
      amount: 500,
      currency: 'USDT',
      bankName: 'GCB Bank',
      accountNumber: '1230998877',
      accountName: 'Kwame Mensah',
      status: 'pending',
    },
  })
  await prisma.withdrawalRequest.create({
    data: {
      userId: chinedu.id,
      amount: 60,
      currency: 'USDT',
      bankName: 'Access Bank',
      accountNumber: '0099887766',
      accountName: 'Chinedu Balogun',
      status: 'pending',
    },
  })

  // Sample AML flag on a user so the UI shows the pattern
  await prisma.amlFlag.create({
    data: {
      userId: chinedu.id,
      type: 'rapid_turnover',
      severity: 'medium',
      description: 'Deposit + withdrawal within 10 minutes, 3 times in 24h.',
    },
  })

  // Provider configs — seed defaults so the admin UI shows all rows.
  await prisma.providerConfig.createMany({
    data: [
      { providerId: 'bitnob', name: 'Bitnob', enabled: true, priority: 8 },
      { providerId: 'transak', name: 'Transak', enabled: true, priority: 5 },
      { providerId: 'coinbase', name: 'Coinbase Commerce', enabled: true, priority: 6 },
      { providerId: 'demo', name: 'AjoVault Demo Rail', enabled: true, priority: 1 },
    ],
  })

  // Country configs — all 12 enabled at launch.
  const iso: [string, number][] = [
    ['NG', 0.5], ['GH', 0.5], ['KE', 0.5], ['ZA', 0.5],
    ['PH', 0.5], ['IN', 0.7], ['ID', 0.7], ['MX', 0.6],
    ['BR', 0.6], ['US', 0.3], ['GB', 0.3], ['EU', 0.3],
  ]
  for (const [code, fee] of iso) {
    await prisma.countryConfig.create({
      data: { countryCode: code, enabled: true, platformFeePct: fee },
    })
  }

  // Platform settings
  await prisma.setting.createMany({
    data: [
      { key: 'platform.feePct', value: '0.5' },
      { key: 'groups.minMembers', value: '5' },
      { key: 'groups.maxMembers', value: '50' },
      { key: 'groups.minContributionUsdt', value: '1' },
      { key: 'groups.maxContributionUsdt', value: '10000' },
      { key: 'groups.frequencies', value: 'weekly,monthly' },
      { key: 'groups.defaultRotation', value: 'rotation' },
      { key: 'disputes.escalationWindowHours', value: '24' },
      { key: 'withdrawals.manualReviewThresholdUsdt', value: '500' },
      { key: 'features.multiAdminGroups', value: 'off' },
      { key: 'features.inAppChat', value: 'off' },
      { key: 'features.smartContractEscrow', value: 'off' },
      { key: 'sms.senderId', value: 'AJOVAULT' },
      { key: 'email.fromAddress', value: 'alerts@ajovault.com' },
    ],
  })

  // Audit seed — show something in the log on first load
  await prisma.auditLog.create({
    data: {
      actorId: adaeze.id,
      action: 'platform.bootstrap',
      target: 'platform',
      details: JSON.stringify({ seededProviders: 4, seededCountries: iso.length }),
    },
  })

  console.log('✅ Seeded successfully')
  console.log('Admin login: adaeze@demo.com / password123')
  console.log('User login: kwame@demo.com / password123')
}

main()
  .catch((e) => {
    console.error(e)
    process.exit(1)
  })
  .finally(async () => {
    await prisma.$disconnect()
  })
