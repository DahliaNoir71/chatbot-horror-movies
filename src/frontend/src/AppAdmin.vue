<script setup lang="ts"></script>

<template>
  <div id="app-shell">
    <main id="main-content">
      <router-view />
    </main>
  </div>
</template>

<style scoped>
#main-content:focus {
  outline: none;
}
</style>
