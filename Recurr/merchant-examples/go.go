// AlgoVoi Tier 2 — Go merchant-side example.
//
// This is a runnable reference showing the full Tier 2 lifecycle from
// the merchant's perspective. The wallet-side flow (where the customer
// actually signs the on-chain authorisation) is documented per chain in
// ../algorand/, ../voi/, ../evm/, ../solana/, ../hedera/, ../stellar/.
//
// This example uses the native-go adapter at ../../native-go/ (v1.2.0+) —
// the chain-agnostic merchant HTTP wrapper. Zero non-stdlib dependencies.
//
// To run:
//
//	cd ../../native-go
//	# Replace api_key / tenant_id / webhook_secret + an existing
//	# subscription_id below, then:
//	go run ../Recurr/merchant-examples/go.go
//
// Or copy this file into your own Go project alongside an import of the
// native-go package.
//
//go:build ignore

package main

import (
	"fmt"
	"sort"

	"algovoi"
)

func main() {
	av := algovoi.New(
		"https://api1.ilovechicken.co.uk",
		"algv_REPLACE_ME",
		"REPLACE_ME_UUID",
		"whsec_REPLACE_ME",
	)

	// Smoke check — list supported chains + event types without any
	// network call.
	fmt.Println("Tier 2 chains supported by this adapter:")
	chains := []string{
		"algorand_mainnet", "algorand_testnet",
		"voi_mainnet", "voi_testnet",
		"base_mainnet", "base_sepolia",
		"tempo_mainnet", "tempo_testnet",
		"solana_mainnet", "solana_devnet",
		"hedera_mainnet", "hedera_testnet",
		"stellar_mainnet", "stellar_testnet",
	}
	sort.Strings(chains)
	for _, c := range chains {
		if algovoi.IsRecurringNetwork(c) {
			fmt.Printf("  - %s\n", c)
		}
	}

	fmt.Println("\nTier 2 webhook event types:")
	events := algovoi.RecurringEventTypes()
	sort.Strings(events)
	for _, e := range events {
		fmt.Printf("  - %s\n", e)
	}

	fmt.Println(
		"\nReady to integrate. Replace the api_key / tenant_id / " +
			"webhook_secret in this file with real values, then call " +
			"createSubscription(av, ...) below to exercise the full lifecycle.",
	)

	// To actually exercise the lifecycle, uncomment + populate:
	//
	//   resp, err := createSubscription(av, "<existing_subscription_uuid>",
	//                                    "X" + strings.Repeat("A", 57),
	//                                    "algorand_mainnet")
	//   if err != nil { log.Fatal(err) }
	//   fmt.Printf("Created authority %s, hand template to wallet:\n  %v\n",
	//              resp.Authority.ID, resp.CustomerSigningPayload)
	_ = av
}

// ---------------------------------------------------------------------------
// Step 1 — Create a Tier 2 standing authority for an existing subscription
// ---------------------------------------------------------------------------

// createSubscription is an example helper. $10/month subscription,
// 12-month standing authority, on the customer's chosen chain.
//
//nolint:unused
func createSubscription(av *algovoi.Client, subscriptionID, customerWallet, chain string) (*algovoi.AuthorityCreateResponse, error) {
	// Cap amounts depend on chain decimals.
	// Most chains: 6 decimals. Stellar: 7 decimals.
	var perCycle, totalCap int64
	if isStellarChain(chain) {
		perCycle = 10 * 10_000_000   // 10 USDC at 7 decimals
		totalCap = 120 * 10_000_000  // 12 months × 10
	} else {
		perCycle = 10 * 1_000_000    // 10 USDC at 6 decimals
		totalCap = 120 * 1_000_000
	}

	return av.CreateRecurringAuthority(algovoi.AuthorityCreateRequest{
		SubscriptionID:        subscriptionID,
		Chain:                 chain,
		CustomerWalletAddress: customerWallet,
		CapAmountMinor:        totalCap,
		CapPeriodSeconds:      365 * 86400,
		PerCycleAmountMinor:   perCycle,
		Asset:                 "USDC",
		Metadata: map[string]interface{}{
			"plan":           "monthly_pro",
			"customer_email": "alice@example.com",
		},
	})
}

// ---------------------------------------------------------------------------
// Step 2-7 — Inspect, manage, revoke (these all work the same way; see
// the per-method docstrings in ../../native-go/recurring.go for full
// details).
// ---------------------------------------------------------------------------

//nolint:unused
func inspectAuthority(av *algovoi.Client, authorityID string) {
	a, err := av.GetAuthority(authorityID)
	if err != nil {
		fmt.Printf("[inspect] error: %v\n", err)
		return
	}
	fmt.Printf("[inspect] status=%s cycles=%d/%d remaining=%d\n",
		a.Status, a.CyclesPulled, a.CyclesPulled+a.CyclesFailed, a.CapRemainingMinor)
}

//nolint:unused
func listActiveAuthorities(av *algovoi.Client) {
	auths, err := av.ListAuthorities(algovoi.ListAuthoritiesOptions{
		Status: "active",
		Limit:  50,
	})
	if err != nil {
		fmt.Printf("[list] error: %v\n", err)
		return
	}
	fmt.Printf("[list] %d active authorities\n", len(auths))
	for _, a := range auths {
		fmt.Printf("    %s  chain=%s  cycles=%d\n", a.ID, a.Chain, a.CyclesPulled)
	}
}

//nolint:unused
func cancelSubscription(av *algovoi.Client, authorityID string) {
	a, err := av.RevokeAuthority(authorityID)
	if err != nil {
		fmt.Printf("[revoke] error: %v\n", err)
		return
	}
	fmt.Printf("[revoke] status=%s\n", a.Status) // 'revoking' → 'revoked' once on-chain
}

func isStellarChain(c string) bool {
	return c == "stellar_mainnet" || c == "stellar_testnet"
}
