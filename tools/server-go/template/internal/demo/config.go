package demo

import (
	"encoding/json"
	"errors"
	"os"
)

type Config struct {
	Version       string `json:"version"`
	StarterReward int64  `json:"starterReward"`
}

func LoadConfig(path string) (Config, error) {
	var c Config
	b, e := os.ReadFile(path)
	if e != nil {
		return c, e
	}
	if e = json.Unmarshal(b, &c); e != nil {
		return c, e
	}
	if c.Version == "" || c.StarterReward <= 0 || c.StarterReward > 1000000 {
		return c, errors.New("invalid formal config")
	}
	return c, nil
}
