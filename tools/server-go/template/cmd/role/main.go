package main

import (
	"example.com/grea/server/internal/platform"
	"log"
	"os"
)

func main() {
	if len(os.Args) != 2 {
		log.Fatal("role required")
	}
	if err := platform.Run(os.Args[1]); err != nil {
		log.Fatal("role startup/runtime failed; inspect dependencies/config")
	}
}
