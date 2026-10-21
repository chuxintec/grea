package demo

import (
	"os"
	"path/filepath"
	"testing"
)

func TestConfigRejectsInvalid(t *testing.T) {
	p := filepath.Join(t.TempDir(), "bad.json")
	os.WriteFile(p, []byte(`{"version":"x","starterReward":-1}`), 0600)
	if _, e := LoadConfig(p); e == nil {
		t.Fatal("bad config cannot fall back")
	}
}
