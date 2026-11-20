import { Canvas, useFrame } from "@react-three/fiber";
import { Component, useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { useNavigate } from "react-router-dom";
import { Poster, Skeleton } from "./Feedback";

function wrapText(context, text, maxWidth, maxLines = 5) {
  const words = String(text || "").split(/\s+/);
  const lines = [];
  let line = "";
  for (const word of words) {
    const test = line ? `${line} ${word}` : word;
    if (context.measureText(test).width > maxWidth && line) {
      lines.push(line);
      line = word;
      if (lines.length >= maxLines) break;
    } else {
      line = test;
    }
  }
  if (line && lines.length < maxLines) lines.push(line);
  return lines;
}

function usePosterTexture(url, title) {
  // Create fallback texture synchronously so cards are never blank white
  const [texture] = useState(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 520;
    canvas.height = 780;
    const ctx = canvas.getContext("2d");
    const gradient = ctx.createLinearGradient(0, 0, 520, 780);
    gradient.addColorStop(0, "#0c0d12");
    gradient.addColorStop(0.55, "#241a17");
    gradient.addColorStop(1, "#08090c");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 520, 780);
    ctx.strokeStyle = "rgba(201,164,92,0.7)";
    ctx.lineWidth = 2;
    ctx.strokeRect(24, 24, 472, 732);
    ctx.fillStyle = "#c9a45c";
    ctx.font = "500 14px Georgia, serif";
    ctx.textAlign = "center";
    ctx.fillText("N O C T U R N E", 260, 82);
    ctx.fillStyle = "#f4f1e8";
    ctx.font = "400 48px Georgia, serif";
    const lines = wrapText(ctx, title || "Nocturne", 400, 4);
    lines.forEach((line, index) => {
      ctx.fillText(line, 260, 360 + index * 58);
    });
    ctx.fillStyle = "rgba(201,164,92,0.75)";
    ctx.fillRect(210, 620, 100, 1);
    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 4;
    return tex;
  });

  useEffect(() => {
    if (!url) return;
    let disposed = false;
    const image = new Image();
    image.crossOrigin = "anonymous";
    image.onload = () => {
      if (disposed) return;
      try {
        const canvas = texture.image;
        canvas.width = 520;
        canvas.height = 780;
        const ctx = canvas.getContext("2d");
        const ratio = Math.max(520 / image.width, 780 / image.height);
        const width = image.width * ratio;
        const height = image.height * ratio;
        ctx.clearRect(0, 0, 520, 780);
        ctx.drawImage(image, (520 - width) / 2, (780 - height) / 2, width, height);
        const shade = ctx.createLinearGradient(0, 520, 0, 780);
        shade.addColorStop(0, "rgba(6,7,10,0)");
        shade.addColorStop(1, "rgba(6,7,10,0.75)");
        ctx.fillStyle = shade;
        ctx.fillRect(0, 0, 520, 780);
        texture.needsUpdate = true;
      } catch {
        // keep fallback
      }
    };
    image.onerror = () => {
      // keep fallback
    };
    image.src = url;
    return () => {
      disposed = true;
      image.src = "";
    };
  }, [url, title, texture]);

  return texture;
}

function PosterCard({ movie, x, hovered }) {
  const group = useRef(null);
  const navigate = useNavigate();
  const texture = usePosterTexture(movie.poster_url, movie.title);
  const baseY = -0.055;
  const baseZ = -0.16;
  const baseRotation = -0.055;

  useFrame((state, delta) => {
    if (!group.current) return;
    const time = state.clock.elapsedTime;
    const float = Math.sin(time * 0.55) * 0.035;
    const targetY = hovered ? baseY + 0.14 : baseY + float;
    const targetZ = hovered ? baseZ + 0.24 : baseZ;
    const targetRotation = hovered ? baseRotation - 0.06 : baseRotation;
    const scale = hovered ? 1.045 : 1;
    group.current.position.y = THREE.MathUtils.damp(group.current.position.y, targetY, 4, delta);
    group.current.position.z = THREE.MathUtils.damp(group.current.position.z, targetZ, 4, delta);
    group.current.rotation.y = THREE.MathUtils.damp(group.current.rotation.y, targetRotation, 4, delta);
    group.current.scale.x = THREE.MathUtils.damp(group.current.scale.x, scale, 5, delta);
    group.current.scale.y = THREE.MathUtils.damp(group.current.scale.y, scale, 5, delta);
    group.current.scale.z = THREE.MathUtils.damp(group.current.scale.z, scale, 5, delta);
  });

  useEffect(() => {
    if (!hovered) document.body.style.cursor = "";
    return () => {
      document.body.style.cursor = "";
    };
  }, [hovered]);

  return (
    <group
      ref={group}
      position={[x, baseY, baseZ]}
      rotation={[0, baseRotation, 0]}
      onClick={(event) => {
        event.stopPropagation();
        navigate(`/movies/${movie.id}`);
      }}
      onPointerOver={(event) => {
        event.stopPropagation();
        document.body.style.cursor = "pointer";
      }}
      onPointerOut={() => {
        document.body.style.cursor = "";
      }}
    >
      <mesh position={[0, 0, -0.045]}>
        <boxGeometry args={[1.54, 2.28, 0.07]} />
        <meshStandardMaterial
          color={hovered ? "#2a2116" : "#16120d"}
          metalness={0.75}
          roughness={0.35}
          emissive={hovered ? "#3b2c11" : "#080706"}
          emissiveIntensity={hovered ? 0.65 : 0.25}
        />
      </mesh>
      <mesh position={[0, 0, 0.004]}>
        <planeGeometry args={[1.43, 2.17]} />
        <meshBasicMaterial map={texture} toneMapped={false} />
      </mesh>
      <mesh position={[0, -1.2, 0.03]}>
        <planeGeometry args={[1.1, 0.004]} />
        <meshBasicMaterial color={hovered ? "#e8cb8e" : "#6d5630"} toneMapped={false} />
      </mesh>
    </group>
  );
}

function Dust() {
  const ref = useRef(null);
  const positions = useMemo(() => {
    const array = new Float32Array(150 * 3);
    for (let i = 0; i < 150; i += 1) {
      array[i * 3] = (Math.random() - 0.5) * 12;
      array[i * 3 + 1] = (Math.random() - 0.5) * 6;
      array[i * 3 + 2] = (Math.random() - 0.5) * 6;
    }
    return array;
  }, []);
  useFrame((state, delta) => {
    if (ref.current) ref.current.rotation.y += delta * 0.012;
  });
  return (
    <points ref={ref}>
      <bufferGeometry>
        <bufferAttribute attach="attributes-position" args={[positions, 3]} />
      </bufferGeometry>
      <pointsMaterial size={0.018} color="#c9a45c" transparent opacity={0.55} depthWrite={false} />
    </points>
  );
}

function CameraDrift() {
  useFrame((state, delta) => {
    const pointer = state.pointer;
    state.camera.position.x = THREE.MathUtils.damp(state.camera.position.x, pointer.x * 0.52, 2.5, delta);
    state.camera.position.y = THREE.MathUtils.damp(state.camera.position.y, 0.3 + pointer.y * 0.22, 2.5, delta);
    state.camera.lookAt(0, -0.05, 0);
  });
  return null;
}

class CanvasBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) return this.props.fallback;
    return this.props.children;
  }
}

export function MovieShelf3D({ movies = [] }) {
  const navigate = useNavigate();
  const [scrollX, setScrollX] = useState(0);
  const [isPaused, setIsPaused] = useState(false);
  const CARD_WIDTH = 1.78;
  const looped = [...movies, ...movies];
  const totalWidth = CARD_WIDTH * looped.length;
  const screenWidth = 5 * CARD_WIDTH; // approx visible width in world units
  const maxScroll = Math.max(0, totalWidth - screenWidth);

  // Auto-scroll right-to-left continuously
  useEffect(() => {
    if (isPaused) return;
    let last = performance.now();
    const frame = (now) => {
      const dt = Math.min((now - last) / 16, 1);
      last = now;
      setScrollX((current) => {
        let next = current - 0.08 * dt;
        if (next <= -maxScroll) next = 0;
        return next;
      });
      if (!isPaused) requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
  }, [isPaused, looped.length]);

  if (!movies.length) {
    return <Skeleton className="shelf-skeleton" />;
  }

  const cards = looped.map((movie, index) => (
    <PosterCard
      key={`${movie.id}-${index}`}
      movie={movie}
      x={index * CARD_WIDTH}
      hovered={false}
    />
  ));

  const fallback = (
    <div className="shelf-fallback">
      {movies.map((movie) => (
        <button key={movie.id} type="button" onClick={() => navigate(`/movies/${movie.id}`)}>
          <Poster src={movie.poster_url} title={movie.title} />
        </button>
      ))}
    </div>
  );

  return (
    <div
      className="shelf-canvas-wrap"
      onPointerEnter={() => setIsPaused(true)}
      onPointerLeave={() => setIsPaused(false)}
    >
      <CanvasBoundary fallback={fallback}>
        <Canvas
          dpr={[1, 1.75]}
          camera={{ position: [0, 0.3, 7.4], fov: 36 }}
          gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
        >
          <fog attach="fog" args={["#06070a", 6.5, 13]} />
          <ambientLight intensity={0.55} />
          <spotLight
            position={[0, 4.5, 5.5]}
            angle={0.65}
            penumbra={1}
            intensity={90}
            color="#f0d6a4"
          />
          <pointLight position={[-4, 1, 3]} intensity={28} color="#6f8ff2" />
          <pointLight position={[4.5, -1, 4]} intensity={18} color="#c9784d" />
          <group position={[scrollX, 0.35, 0]}>
            {cards}
          </group>
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -1.36, 0.3]}>
            <planeGeometry args={[18, 9]} />
            <meshStandardMaterial color="#07080b" metalness={0.85} roughness={0.32} />
          </mesh>
          <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -1.35, 0.3]}>
            <ringGeometry args={[2.9, 3.0, 96]} />
            <meshBasicMaterial color="#3a2e1b" transparent opacity={0.5} />
          </mesh>
          <Dust />
          <CameraDrift />
        </Canvas>
      </CanvasBoundary>
      <div className="shelf-mobile">{fallback}</div>
      <div className="shelf-caption">
        <span>Now on the shelf</span>
        <span className="shelf-caption-line" />
        <span>Hover any card to stop</span>
      </div>
    </div>
  );
}
